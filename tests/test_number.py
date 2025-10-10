"""Tests for Moodo number platform."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN, ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.moodo.api import MoodoConnectionError
from custom_components.moodo.const import DOMAIN
from custom_components.moodo.coordinator import MoodoDataUpdateCoordinator


@pytest.fixture
async def setup_number_platform(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_coordinator_data: dict[int, dict[str, Any]],
    mock_websocket_factory: MagicMock,
) -> MoodoDataUpdateCoordinator:
    """Set up the number platform for testing."""
    mock_config_entry.add_to_hass(hass)

    # Set up the number platform with proper mocking
    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator that was created
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    return coordinator


async def test_number_setup(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test number setup creates entities."""
    entity_registry = er.async_get(hass)

    # Check all 4 capsule intensity entities
    for slot_id in range(4):
        entity = entity_registry.async_get(f"number.living_room_capsule_{slot_id + 1}_intensity")
        assert entity is not None
        assert entity.unique_id == f"12345_slot_{slot_id}_intensity"


async def test_number_state(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test number entity state."""
    state = hass.states.get("number.living_room_capsule_1_intensity")
    assert state is not None
    # Default fan_speed is 50
    assert state.state == "50"
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 100
    assert state.attributes["step"] == 1
    assert state.attributes["mode"] == "slider"
    assert state.attributes["friendly_name"] == "Living Room Capsule 1 Intensity"


async def test_number_set_value(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test setting number value."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.living_room_capsule_1_intensity", ATTR_VALUE: 75},
        blocking=True,
    )

    # Should call set_fan_speeds with correct slot settings
    call_args = mock_moodo_api_client.set_fan_speeds.call_args
    assert call_args is not None
    device_key, slot_settings = call_args[0]
    assert device_key == 12345
    assert 0 in slot_settings
    assert slot_settings[0]["fan_speed"] == 75
    assert slot_settings[0]["fan_active"] is True

    # Check optimistic update
    state = hass.states.get("number.living_room_capsule_1_intensity")
    assert state.state == "75"


async def test_number_set_value_zero(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test setting number value to 0 sets fan_active to False."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.living_room_capsule_2_intensity", ATTR_VALUE: 0},
        blocking=True,
    )

    # Should call set_fan_speeds with fan_active=False
    call_args = mock_moodo_api_client.set_fan_speeds.call_args
    assert call_args is not None
    device_key, slot_settings = call_args[0]
    assert device_key == 12345
    assert 1 in slot_settings  # Capsule 2 is slot_id 1
    assert slot_settings[1]["fan_speed"] == 0
    assert slot_settings[1]["fan_active"] is False


async def test_number_set_value_error(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test error handling when setting value fails."""
    mock_moodo_api_client.set_fan_speeds.side_effect = MoodoConnectionError("Connection failed")

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.living_room_capsule_1_intensity", ATTR_VALUE: 50},
        blocking=True,
    )

    # Should request refresh after error
    mock_moodo_api_client.get_boxes.assert_called()


async def test_number_unavailable_when_offline(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test number entities become unavailable when device is offline."""
    coordinator = setup_number_platform

    # Set device to offline
    mock_coordinator_data[12345]["is_online"] = False
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("number.living_room_capsule_1_intensity")
    assert state.state == "unavailable"


async def test_number_unavailable_when_slider_not_movable(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test number entities become unavailable when slider is not movable."""
    coordinator = setup_number_platform

    # Set is_fan_slider_movable to False for slot 0
    mock_coordinator_data[12345]["settings"][0]["is_fan_slider_movable"] = False
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("number.living_room_capsule_1_intensity")
    assert state.state == "unavailable"


async def test_number_extra_state_attributes(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test number entity extra state attributes."""
    state = hass.states.get("number.living_room_capsule_1_intensity")
    assert state is not None
    # slot_id should be present
    assert state.attributes["slot_id"] == 0


async def test_number_device_info(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test number device info."""
    entity_registry = er.async_get(hass)
    device_registry = hass.helpers.device_registry.async_get(hass)

    entity = entity_registry.async_get("number.living_room_capsule_1_intensity")
    assert entity is not None

    device = device_registry.async_get(entity.device_id)
    assert device is not None
    assert device.name == "Living Room"
    assert device.manufacturer == "Moodo"
    assert device.model == "Box v2"
    assert (DOMAIN, 12345) in device.identifiers
    assert (DOMAIN, "box_id_1") in device.identifiers


async def test_number_preserves_other_slot_settings(
    hass: HomeAssistant,
    setup_number_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test that setting one slot's value preserves other slots."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.living_room_capsule_1_intensity", ATTR_VALUE: 100},
        blocking=True,
    )

    # Should include all 4 slots
    call_args = mock_moodo_api_client.set_fan_speeds.call_args
    assert call_args is not None
    device_key, slot_settings = call_args[0]
    assert len(slot_settings) == 4
    # Slot 0 should be updated
    assert slot_settings[0]["fan_speed"] == 100
    # Other slots should maintain their values
    assert slot_settings[1]["fan_speed"] == 50
    assert slot_settings[2]["fan_speed"] == 50
    assert slot_settings[3]["fan_speed"] == 50
