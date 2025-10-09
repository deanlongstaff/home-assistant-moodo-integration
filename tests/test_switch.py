"""Tests for Moodo switch platform."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.moodo.api import MoodoConnectionError
from custom_components.moodo.const import DOMAIN
from custom_components.moodo.coordinator import MoodoDataUpdateCoordinator


@pytest.fixture
async def setup_switch_platform(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_coordinator_data: dict[int, dict[str, Any]],
    mock_websocket_factory: MagicMock,
) -> MoodoDataUpdateCoordinator:
    """Set up the switch platform for testing."""
    mock_config_entry.add_to_hass(hass)

    # Set up the switch platform with proper mocking
    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator that was created
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    return coordinator


async def test_switch_setup(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test switch setup creates entities."""
    entity_registry = er.async_get(hass)

    # Check shuffle switch
    shuffle_entity = entity_registry.async_get("switch.living_room_shuffle")
    assert shuffle_entity is not None
    assert shuffle_entity.unique_id == "12345_shuffle"

    # Check interval switch
    interval_entity = entity_registry.async_get("switch.living_room_interval")
    assert interval_entity is not None
    assert interval_entity.unique_id == "12345_interval"


async def test_shuffle_switch_state(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test shuffle switch state."""
    state = hass.states.get("switch.living_room_shuffle")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["friendly_name"] == "Living Room Shuffle"


async def test_interval_switch_state(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test interval switch state."""
    state = hass.states.get("switch.living_room_interval")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes["friendly_name"] == "Living Room Interval"
    assert state.attributes["can_turn_on"] is True


async def test_interval_switch_cannot_turn_on(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test interval switch when it cannot be turned on."""
    coordinator = setup_switch_platform

    # Update data to set can_interval_turn_on to False
    mock_coordinator_data[12345]["can_interval_turn_on"] = False
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.living_room_interval")
    assert state is not None
    assert state.attributes["can_turn_on"] is False
    assert state.attributes["note"] == "Interval mode unavailable for current capsule configuration"


async def test_shuffle_turn_on(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test turning on shuffle switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.living_room_shuffle"},
        blocking=True,
    )

    mock_moodo_api_client.enable_shuffle.assert_called_once_with(12345)

    # Check optimistic update
    state = hass.states.get("switch.living_room_shuffle")
    assert state.state == STATE_ON


async def test_shuffle_turn_off(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test turning off shuffle switch."""
    coordinator = setup_switch_platform

    # First turn it on
    mock_coordinator_data[12345]["shuffle"] = True
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.living_room_shuffle")
    assert state.state == STATE_ON

    # Now turn it off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.living_room_shuffle"},
        blocking=True,
    )

    mock_moodo_api_client.disable_shuffle.assert_called_once_with(12345)

    # Check optimistic update
    state = hass.states.get("switch.living_room_shuffle")
    assert state.state == STATE_OFF


async def test_interval_turn_on(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test turning on interval switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.living_room_interval"},
        blocking=True,
    )

    mock_moodo_api_client.enable_interval.assert_called_once_with(12345)

    # Check optimistic update
    state = hass.states.get("switch.living_room_interval")
    assert state.state == STATE_ON


async def test_interval_turn_off(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test turning off interval switch."""
    coordinator = setup_switch_platform

    # First turn it on
    mock_coordinator_data[12345]["interval"] = True
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.living_room_interval")
    assert state.state == STATE_ON

    # Now turn it off
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.living_room_interval"},
        blocking=True,
    )

    mock_moodo_api_client.disable_interval.assert_called_once_with(12345)

    # Check optimistic update
    state = hass.states.get("switch.living_room_interval")
    assert state.state == STATE_OFF


async def test_switch_turn_on_error(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test error handling when turning on switch fails."""
    mock_moodo_api_client.enable_shuffle.side_effect = MoodoConnectionError("Connection failed")
    mock_moodo_api_client.get_boxes.return_value = [
        {
            "device_key": 12345,
            "shuffle": False,
        }
    ]

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.living_room_shuffle"},
        blocking=True,
    )

    # Should request refresh after error
    mock_moodo_api_client.get_boxes.assert_called()


async def test_switch_turn_off_error(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test error handling when turning off switch fails."""
    coordinator = setup_switch_platform

    # Set switch to on
    mock_coordinator_data[12345]["shuffle"] = True
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    mock_moodo_api_client.disable_shuffle.side_effect = MoodoConnectionError("Connection failed")
    mock_moodo_api_client.get_boxes.return_value = [
        {
            "device_key": 12345,
            "shuffle": True,
        }
    ]

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.living_room_shuffle"},
        blocking=True,
    )

    # Should request refresh after error
    mock_moodo_api_client.get_boxes.assert_called()


async def test_switch_unavailable_when_offline(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test switches become unavailable when device is offline."""
    coordinator = setup_switch_platform

    # Set device to offline
    mock_coordinator_data[12345]["is_online"] = False
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("switch.living_room_shuffle")
    assert state.state == "unavailable"

    state = hass.states.get("switch.living_room_interval")
    assert state.state == "unavailable"


async def test_switch_device_info(
    hass: HomeAssistant,
    setup_switch_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test switch device info."""
    entity_registry = er.async_get(hass)
    device_registry = hass.helpers.device_registry.async_get(hass)

    entity = entity_registry.async_get("switch.living_room_shuffle")
    assert entity is not None

    device = device_registry.async_get(entity.device_id)
    assert device is not None
    assert device.name == "Living Room"
    assert device.manufacturer == "Moodo"
    assert device.model == "Box v2"
    assert (DOMAIN, 12345) in device.identifiers
    assert (DOMAIN, "box_id_1") in device.identifiers
