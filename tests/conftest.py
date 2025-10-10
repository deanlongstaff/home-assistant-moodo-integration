"""Pytest fixtures for Moodo integration tests."""
from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moodo.const import CONF_TOKEN, DOMAIN

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations defined in the test dir."""
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Moodo",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password123",
            CONF_TOKEN: "test_token_12345",
        },
        unique_id="test@example.com",
    )


@pytest.fixture
def mock_moodo_api_client() -> MagicMock:
    """Return a mock Moodo API client."""
    client = MagicMock()
    client.login = AsyncMock(return_value="test_token_12345")
    client.get_boxes = AsyncMock(return_value=[
        {
            "device_key": 12345,
            "id": "box_id_1",
            "name": "Living Room",
            "is_online": True,
            "box_status": 0,
            "box_version": 2,
            "shuffle": False,
            "interval": False,
            "fan_volume": 50,
            "box_mode": "diffuser",
            "can_interval_turn_on": True,
            "has_battery": False,
            "settings": [
                {"slot_id": 0, "slot": 0, "fan_speed": 50, "fan_active": True, "capsule_type_code": "C01", "capsule_info": {}},
                {"slot_id": 1, "slot": 1, "fan_speed": 50, "fan_active": True, "capsule_type_code": "C02", "capsule_info": {}},
                {"slot_id": 2, "slot": 2, "fan_speed": 50, "fan_active": True, "capsule_type_code": "C03", "capsule_info": {}},
                {"slot_id": 3, "slot": 3, "fan_speed": 50, "fan_active": True, "capsule_type_code": "C04", "capsule_info": {}},
            ],
        }
    ])
    client.get_interval_types = AsyncMock(return_value=[
        {"type": 1, "name": "Short", "duration": 300},
        {"type": 2, "name": "Medium", "duration": 600},
        {"type": 3, "name": "Long", "duration": 900},
    ])
    client.get_favorites = AsyncMock(return_value=[
        {
            "id": "fav_1",
            "title": "Favorite 1",
            "name": "Favorite 1",
            "settings": [
                {"slot": 0, "capsule_type_code": "C01", "fan_speed": 50, "fan_active": True},
                {"slot": 1, "capsule_type_code": "C02", "fan_speed": 50, "fan_active": True},
                {"slot": 2, "capsule_type_code": "C03", "fan_speed": 50, "fan_active": True},
                {"slot": 3, "capsule_type_code": "C04", "fan_speed": 50, "fan_active": True},
            ],
        }
    ])
    client.enable_shuffle = AsyncMock(return_value={"box": {"shuffle": True}})
    client.disable_shuffle = AsyncMock(return_value={"box": {"shuffle": False}})
    client.enable_interval = AsyncMock(return_value={"box": {"interval": True}})
    client.disable_interval = AsyncMock(return_value={"box": {"interval": False}})
    client.power_on_box = AsyncMock(return_value={"box": {"box_status": 1}})
    client.power_off_box = AsyncMock(return_value={"box": {"box_status": 0}})
    client.set_fan_volume = AsyncMock(return_value={"box": {"fan_volume": 75}})
    client.set_box_mode = AsyncMock(return_value={"box": {"box_mode": "purifier"}})
    client.set_fan_speeds = AsyncMock(return_value={"box": {}})
    client.apply_favorite = AsyncMock(return_value={"box": {}})
    client.should_ignore_websocket_event = MagicMock(return_value=False)

    return client


@pytest.fixture
def mock_moodo_websocket() -> MagicMock:
    """Return a mock Moodo WebSocket."""
    websocket = MagicMock()
    websocket.connect = AsyncMock()
    websocket.disconnect = AsyncMock()
    websocket.connect.return_value = None
    websocket.disconnect.return_value = None
    return websocket


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.moodo.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_api_client_factory(mock_moodo_api_client: MagicMock) -> Generator[MagicMock, None, None]:
    """Mock the MoodoAPIClient class."""
    with patch(
        "custom_components.moodo.api.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ) as mock_factory:
        yield mock_factory


@pytest.fixture
def mock_websocket_factory(mock_moodo_websocket: MagicMock) -> Generator[MagicMock, None, None]:
    """Mock the MoodoWebSocket class."""
    with patch(
        "custom_components.moodo.coordinator.MoodoWebSocket",
        return_value=mock_moodo_websocket,
    ) as mock_factory:
        yield mock_factory


@pytest.fixture
def mock_coordinator_data() -> dict[int, dict[str, Any]]:
    """Return mock coordinator data."""
    return {
        12345: {
            "device_key": 12345,
            "id": "box_id_1",
            "name": "Living Room",
            "is_online": True,
            "box_status": 0,
            "box_version": 2,
            "shuffle": False,
            "interval": False,
            "fan_volume": 50,
            "box_mode": "diffuser",
            "can_interval_turn_on": True,
            "has_battery": False,
            "settings": [
                {"slot_id": 0, "slot": 0, "fan_speed": 50, "fan_active": True, "capsule_type_code": "C01", "capsule_info": {}},
                {"slot_id": 1, "slot": 1, "fan_speed": 50, "fan_active": True, "capsule_type_code": "C02", "capsule_info": {}},
                {"slot_id": 2, "slot": 2, "fan_speed": 50, "fan_active": True, "capsule_type_code": "C03", "capsule_info": {}},
                {"slot_id": 3, "slot": 3, "fan_speed": 50, "fan_active": True, "capsule_type_code": "C04", "capsule_info": {}},
            ],
        }
    }
