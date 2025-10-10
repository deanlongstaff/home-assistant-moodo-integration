"""Tests for Moodo sensor platform."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.moodo.const import DOMAIN
from custom_components.moodo.coordinator import MoodoDataUpdateCoordinator


@pytest.fixture
async def setup_sensor_platform(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_coordinator_data: dict[int, dict[str, Any]],
    mock_websocket_factory: MagicMock,
) -> MoodoDataUpdateCoordinator:
    """Set up the sensor platform for testing."""
    mock_config_entry.add_to_hass(hass)

    # Set up the sensor platform with proper mocking
    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Get the coordinator that was created
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    return coordinator


async def test_sensor_setup(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test sensor setup creates entities."""
    entity_registry = er.async_get(hass)

    # Check standard sensors
    battery_entity = entity_registry.async_get("sensor.living_room_battery_level")
    assert battery_entity is not None
    assert battery_entity.unique_id == "12345_battery_level"

    adapter_entity = entity_registry.async_get("sensor.living_room_adapter_status")
    assert adapter_entity is not None
    assert adapter_entity.unique_id == "12345_is_adapter_on"

    charging_entity = entity_registry.async_get("sensor.living_room_charging_status")
    assert charging_entity is not None
    assert charging_entity.unique_id == "12345_is_battery_charging"

    preset_entity = entity_registry.async_get("sensor.living_room_active_preset")
    assert preset_entity is not None
    assert preset_entity.unique_id == "12345_favorite_id_applied"

    # Check capsule sensors (4 slots, each has type and remaining)
    for slot_id in range(4):
        type_entity = entity_registry.async_get(f"sensor.living_room_capsule_{slot_id + 1}_type")
        assert type_entity is not None
        assert type_entity.unique_id == f"12345_capsule_{slot_id}_type"

        remaining_entity = entity_registry.async_get(f"sensor.living_room_capsule_{slot_id + 1}_remaining")
        assert remaining_entity is not None
        assert remaining_entity.unique_id == f"12345_capsule_{slot_id}_remaining"


async def test_adapter_status_sensor(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test adapter status sensor."""
    state = hass.states.get("sensor.living_room_adapter_status")
    assert state is not None
    assert state.state == "off"
    assert state.attributes["friendly_name"] == "Living Room Adapter Status"


async def test_charging_status_sensor(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test charging status sensor."""
    state = hass.states.get("sensor.living_room_charging_status")
    assert state is not None
    # Unavailable when has_battery is False
    assert state.state == "unavailable"
    assert state.attributes["friendly_name"] == "Living Room Charging Status"


async def test_active_preset_sensor(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test active preset sensor."""
    state = hass.states.get("sensor.living_room_active_preset")
    assert state is not None
    assert state.state == "None"
    assert state.attributes["friendly_name"] == "Living Room Active Preset"


async def test_active_preset_sensor_with_favorite(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test active preset sensor shows favorite title."""
    coordinator = setup_sensor_platform

    # Set an active favorite
    mock_coordinator_data[12345]["favorite_id_applied"] = "fav_1"
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_active_preset")
    assert state.state == "Favorite 1"
    assert state.attributes["preset_id"] == "fav_1"


async def test_capsule_type_sensor(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test capsule type sensor."""
    state = hass.states.get("sensor.living_room_capsule_1_type")
    assert state is not None
    assert state.state == "Empty"
    assert state.attributes["friendly_name"] == "Living Room Capsule 1 Type"


async def test_capsule_remaining_sensor(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test capsule remaining sensor."""
    state = hass.states.get("sensor.living_room_capsule_1_remaining")
    assert state is not None
    # Should be unknown when no fragrance data
    assert state.state == "unknown"
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["device_class"] == "battery"
    assert state.attributes["friendly_name"] == "Living Room Capsule 1 Remaining"


async def test_battery_level_unavailable_when_no_battery(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test battery level sensor is unavailable when device has no battery."""
    # Default mock data has has_battery=False
    state = hass.states.get("sensor.living_room_battery_level")
    assert state.state == "unavailable"


async def test_battery_level_available_when_has_battery(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test battery level sensor is available when device has battery."""
    coordinator = setup_sensor_platform

    # Add battery data
    mock_coordinator_data[12345]["has_battery"] = True
    mock_coordinator_data[12345]["battery_level_percent"] = 85
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_battery_level")
    assert state.state == "85"
    assert state.attributes["unit_of_measurement"] == "%"
    assert state.attributes["device_class"] == "battery"


async def test_charging_status_unavailable_when_no_battery(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test charging status sensor is unavailable when device has no battery."""
    state = hass.states.get("sensor.living_room_charging_status")
    assert state.state == "unavailable"


async def test_charging_status_available_when_has_battery(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test charging status sensor is available when device has battery."""
    coordinator = setup_sensor_platform

    # Add battery data
    mock_coordinator_data[12345]["has_battery"] = True
    mock_coordinator_data[12345]["is_battery_charging"] = True
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_charging_status")
    assert state.state == "charging"


async def test_adapter_status_on_when_charging(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test adapter status shows 'on' when battery is charging."""
    coordinator = setup_sensor_platform

    # Set charging to True
    mock_coordinator_data[12345]["is_battery_charging"] = True
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_adapter_status")
    # Should show 'on' because charging implies adapter is on
    assert state.state == "on"


async def test_battery_level_100_when_charging_with_0(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test battery level shows 100% when charging and API reports 0."""
    coordinator = setup_sensor_platform

    # Add battery data - charging with 0% (API quirk)
    mock_coordinator_data[12345]["has_battery"] = True
    mock_coordinator_data[12345]["battery_level_percent"] = 0
    mock_coordinator_data[12345]["is_battery_charging"] = True
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_battery_level")
    # Should report 100% when charging and battery is 0
    assert state.state == "100"


async def test_sensors_unavailable_when_offline(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test sensors become unavailable when device is offline."""
    coordinator = setup_sensor_platform

    # Set device to offline
    mock_coordinator_data[12345]["is_online"] = False
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_adapter_status")
    assert state.state == "unavailable"

    state = hass.states.get("sensor.living_room_capsule_1_type")
    assert state.state == "unavailable"


async def test_sensor_device_info(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
) -> None:
    """Test sensor device info."""
    entity_registry = er.async_get(hass)
    device_registry = hass.helpers.device_registry.async_get(hass)

    entity = entity_registry.async_get("sensor.living_room_adapter_status")
    assert entity is not None

    device = device_registry.async_get(entity.device_id)
    assert device is not None
    assert device.name == "Living Room"
    assert device.manufacturer == "Moodo"
    assert device.model == "Box v2"
    assert (DOMAIN, 12345) in device.identifiers
    assert (DOMAIN, "box_id_1") in device.identifiers


async def test_capsule_remaining_sensor_with_fragrance_data(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test capsule remaining sensor with actual fragrance data."""
    coordinator = setup_sensor_platform

    # Add fragrance data to slot 0
    mock_coordinator_data[12345]["settings"][0]["fragrance_left_percent"] = 75.5
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_capsule_1_remaining")
    # Should round to 76
    assert state.state == "76"
    assert state.attributes["fragrance_left_percent"] == 75.5
    assert state.attributes["source"] == "actual_remaining"


async def test_capsule_remaining_sensor_fallback_to_manual(
    hass: HomeAssistant,
    setup_sensor_platform: MoodoDataUpdateCoordinator,
    mock_coordinator_data: dict[int, dict[str, Any]],
) -> None:
    """Test capsule remaining sensor falls back to manual usage."""
    coordinator = setup_sensor_platform

    # Add only manual usage data (no fragrance_left_percent)
    mock_coordinator_data[12345]["settings"][0]["slot_manual_usage_percent"] = 50.0
    coordinator.async_set_updated_data(mock_coordinator_data)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room_capsule_1_remaining")
    assert state.state == "50"
    assert state.attributes["slot_manual_usage_percent"] == 50.0
    assert state.attributes["source"] == "manual_setting"
