"""Tests for Moodo select platform."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN, ATTR_OPTION, SERVICE_SELECT_OPTION
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.moodo.api import MoodoConnectionError
from custom_components.moodo.const import DOMAIN
from custom_components.moodo.coordinator import MoodoDataUpdateCoordinator


@pytest.fixture
async def setup_select_platform(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_coordinator_data: dict[int, dict[str, Any]],
    mock_websocket_factory: MagicMock,
) -> MoodoDataUpdateCoordinator:
    """Set up the select platform for testing."""
    mock_config_entry.add_to_hass(hass)

    # Set up the select platform with proper mocking
    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator that was created
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    return coordinator


async def test_select_setup(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test select setup creates entities."""
    entity_registry = er.async_get(hass)

    # Check box mode select
    mode_entity = entity_registry.async_get("select.living_room_mode")
    assert mode_entity is not None
    assert mode_entity.unique_id == "12345_box_mode"

    # Check interval type select
    interval_type_entity = entity_registry.async_get("select.living_room_interval_type")
    assert interval_type_entity is not None
    assert interval_type_entity.unique_id == "12345_interval_type"

    # Check preset select
    preset_entity = entity_registry.async_get("select.living_room_preset")
    assert preset_entity is not None
    assert preset_entity.unique_id == "12345_preset"


async def test_box_mode_select_state(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test box mode select state."""
    state = hass.states.get("select.living_room_mode")
    assert state is not None
    assert state.state == "diffuser"
    assert "diffuser" in state.attributes["options"]
    assert state.attributes["friendly_name"] == "Living Room Mode"


async def test_box_mode_select_option(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test selecting box mode option."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.living_room_mode", ATTR_OPTION: "diffuser"},
        blocking=True,
    )

    mock_moodo_api_client.set_box_mode.assert_called_once_with(12345, "diffuser")


async def test_box_mode_select_error(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test error handling when selecting box mode fails."""
    mock_moodo_api_client.set_box_mode.side_effect = MoodoConnectionError("Connection failed")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.living_room_mode", ATTR_OPTION: "diffuser"},
        blocking=True,
    )

    # Should request refresh after error
    mock_moodo_api_client.get_boxes.assert_called()


async def test_interval_type_select_state(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test interval type select state."""
    state = hass.states.get("select.living_room_interval_type")
    assert state is not None
    # Options should be based on interval types (1, 2, 3)
    assert len(state.attributes["options"]) == 3
    assert state.attributes["friendly_name"] == "Living Room Interval Type"


async def test_interval_type_unavailable_when_interval_off(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test interval type select is unavailable when interval mode is off."""
    coordinator = setup_select_platform

    # Interval is False by default
    state = hass.states.get("select.living_room_interval_type")
    assert state.state == "unavailable"

    # Enable interval
    mock_coordinator_data[12345]["interval"] = True
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("select.living_room_interval_type")
    assert state.state != "unavailable"


async def test_preset_select_state(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test preset select state."""
    state = hass.states.get("select.living_room_preset")
    assert state is not None
    # Should have 1 favorite available
    assert len(state.attributes["options"]) == 1
    assert "Favorite 1" in state.attributes["options"]
    assert state.attributes["friendly_name"] == "Living Room Preset"


async def test_preset_select_option(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test selecting preset option."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.living_room_preset", ATTR_OPTION: "Favorite 1"},
        blocking=True,
    )

    mock_moodo_api_client.apply_favorite.assert_called_once_with("fav_1", 12345)


async def test_preset_select_optimistic_update(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test preset selection updates state optimistically."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.living_room_preset", ATTR_OPTION: "Favorite 1"},
        blocking=True,
    )

    # Check optimistic update
    state = hass.states.get("select.living_room_preset")
    assert state.state == "Favorite 1"


async def test_preset_select_unavailable_when_no_matching_presets(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test preset select is unavailable when no presets match capsules."""
    coordinator = setup_select_platform

    # Change capsule codes so they don't match the favorite
    mock_coordinator_data[12345]["settings"][0]["capsule_type_code"] = "C99"
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("select.living_room_preset")
    assert state.state == "unavailable"


async def test_preset_select_error(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test error handling when selecting preset fails."""
    mock_moodo_api_client.apply_favorite.side_effect = MoodoConnectionError("Connection failed")

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.living_room_preset", ATTR_OPTION: "Favorite 1"},
        blocking=True,
    )

    # Should request refresh after error
    mock_moodo_api_client.get_boxes.assert_called()


async def test_select_unavailable_when_offline(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test select entities become unavailable when device is offline."""
    coordinator = setup_select_platform

    # Set device to offline
    mock_coordinator_data[12345]["is_online"] = False
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("select.living_room_mode")
    assert state.state == "unavailable"


async def test_select_device_info(
    hass: HomeAssistant,
    setup_select_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test select device info."""
    entity_registry = er.async_get(hass)
    device_registry = hass.helpers.device_registry.async_get(hass)

    entity = entity_registry.async_get("select.living_room_mode")
    assert entity is not None

    device = device_registry.async_get(entity.device_id)
    assert device is not None
    assert device.name == "Living Room"
    assert device.manufacturer == "Moodo"
    assert device.model == "Box v2"
    assert (DOMAIN, 12345) in device.identifiers
    assert (DOMAIN, "box_id_1") in device.identifiers
