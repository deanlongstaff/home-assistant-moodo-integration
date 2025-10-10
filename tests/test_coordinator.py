"""Tests for Moodo data update coordinator."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moodo.api import MoodoAuthError, MoodoConnectionError
from custom_components.moodo.coordinator import MoodoDataUpdateCoordinator


async def test_coordinator_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator initialization."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    assert coordinator.client == mock_moodo_api_client
    assert coordinator.interval_types == {}
    assert coordinator.favorites == {}
    assert coordinator.websocket is None


async def test_coordinator_update_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator data update."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    await coordinator.async_config_entry_first_refresh()

    # Should have fetched boxes
    mock_moodo_api_client.get_boxes.assert_called_once()

    # Data should be indexed by device_key
    assert 12345 in coordinator.data
    assert coordinator.data[12345]["name"] == "Living Room"


async def test_coordinator_fetch_interval_types(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator fetches interval types."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    await coordinator.async_config_entry_first_refresh()

    # Should have fetched interval types
    mock_moodo_api_client.get_interval_types.assert_called_once()

    # Interval types should be indexed by type
    assert 1 in coordinator.interval_types
    assert coordinator.interval_types[1]["name"] == "Short"


async def test_coordinator_fetch_favorites(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator fetches favorites."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    await coordinator.async_config_entry_first_refresh()

    # Should have fetched favorites
    mock_moodo_api_client.get_favorites.assert_called_once()

    # Favorites should be indexed by id
    assert "fav_1" in coordinator.favorites
    assert coordinator.favorites["fav_1"]["name"] == "Favorite 1"


async def test_coordinator_update_data_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator handles authentication errors."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    mock_moodo_api_client.get_boxes.side_effect = MoodoAuthError("Token expired")

    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()


async def test_coordinator_update_data_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator handles connection errors during first refresh."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    mock_moodo_api_client.get_boxes.side_effect = MoodoConnectionError("Connection timeout")

    # During first refresh, UpdateFailed is automatically converted to ConfigEntryNotReady
    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_config_entry_first_refresh()


async def test_coordinator_update_box_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator optimistic update."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    await coordinator.async_config_entry_first_refresh()

    # Optimistically update box data
    coordinator.update_box_data(12345, {"shuffle": True})

    assert coordinator.data[12345]["shuffle"] is True


async def test_coordinator_get_available_favorites(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test getting available favorites for a device."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    await coordinator.async_config_entry_first_refresh()

    # Get available favorites
    available = coordinator.get_available_favorites(12345)

    # Should include favorite that matches capsules
    assert "fav_1" in available


async def test_coordinator_get_available_favorites_no_match(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test getting available favorites when capsules don't match."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    # Modify favorites to have different capsules
    mock_moodo_api_client.get_favorites.return_value = [
        {
            "id": "fav_2",
            "name": "Favorite 2",
            "settings": [
                {"slot": 0, "capsule_type_code": "C05"},
                {"slot": 1, "capsule_type_code": "C06"},
                {"slot": 2, "capsule_type_code": "C07"},
                {"slot": 3, "capsule_type_code": "C08"},
            ],
        }
    ]

    await coordinator.async_config_entry_first_refresh()

    # Get available favorites
    available = coordinator.get_available_favorites(12345)

    # Should not include favorite with different capsules
    assert len(available) == 0


async def test_coordinator_websocket_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_moodo_websocket: MagicMock,
) -> None:
    """Test WebSocket setup."""
    mock_config_entry.add_to_hass(hass)
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )
    # Manually set config_entry since parent class overrides it
    coordinator.config_entry = mock_config_entry

    await coordinator.async_config_entry_first_refresh()

    with patch(
        "custom_components.moodo.coordinator.MoodoWebSocket",
        return_value=mock_moodo_websocket,
    ) as mock_ws_class:
        await coordinator._async_setup_websocket()

    # WebSocket should be created and connected
    mock_ws_class.assert_called_once()
    mock_moodo_websocket.connect.assert_called_once()
    assert coordinator.websocket == mock_moodo_websocket


async def test_coordinator_websocket_setup_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_moodo_websocket: MagicMock,
) -> None:
    """Test WebSocket setup failure is handled gracefully."""
    mock_config_entry.add_to_hass(hass)
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )
    # Manually set config_entry since parent class overrides it
    coordinator.config_entry = mock_config_entry

    await coordinator.async_config_entry_first_refresh()

    # Create a new mock that fails on connect
    failing_websocket = MagicMock()
    failing_websocket.connect = AsyncMock(side_effect=Exception("Connection failed"))

    with patch(
        "custom_components.moodo.coordinator.MoodoWebSocket",
        return_value=failing_websocket,
    ):
        await coordinator._async_setup_websocket()

    # WebSocket should be None after failure
    assert coordinator.websocket is None


async def test_coordinator_handle_websocket_message(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test handling WebSocket messages."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    await coordinator.async_config_entry_first_refresh()

    # Handle WebSocket message
    updated_box = {
        "device_key": 12345,
        "shuffle": True,
        "interval": False,
    }

    await coordinator._handle_websocket_message(updated_box)

    # Data should be updated
    assert coordinator.data[12345]["shuffle"] is True


async def test_coordinator_handle_websocket_message_ignore_own_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test WebSocket messages from own actions are ignored."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    await coordinator.async_config_entry_first_refresh()

    # Mock should_ignore_websocket_event to return True
    mock_moodo_api_client.should_ignore_websocket_event.return_value = True

    original_shuffle = coordinator.data[12345]["shuffle"]

    # Handle WebSocket message with request_id
    updated_box = {
        "device_key": 12345,
        "shuffle": True,
    }

    await coordinator._handle_websocket_message(updated_box, request_id="test_request_id")

    # Data should not be updated
    assert coordinator.data[12345]["shuffle"] == original_shuffle


async def test_coordinator_shutdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_moodo_websocket: MagicMock,
) -> None:
    """Test coordinator shutdown."""
    mock_config_entry.add_to_hass(hass)
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )
    # Manually set config_entry since parent class overrides it
    coordinator.config_entry = mock_config_entry

    await coordinator.async_config_entry_first_refresh()

    with patch(
        "custom_components.moodo.coordinator.MoodoWebSocket",
        return_value=mock_moodo_websocket,
    ):
        await coordinator._async_setup_websocket()

    # Shutdown coordinator
    await coordinator.async_shutdown()

    # WebSocket should be disconnected
    mock_moodo_websocket.disconnect.assert_called_once()
    assert coordinator.websocket is None


async def test_coordinator_interval_types_fetch_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator handles interval types fetch failure gracefully."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    mock_moodo_api_client.get_interval_types.side_effect = Exception("Fetch failed")

    # Should not raise, just log warning
    await coordinator.async_config_entry_first_refresh()

    # Interval types should be empty
    assert len(coordinator.interval_types) == 0


async def test_coordinator_favorites_fetch_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test coordinator handles favorites fetch failure gracefully."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    mock_moodo_api_client.get_favorites.side_effect = Exception("Fetch failed")

    # Should not raise, just log warning
    await coordinator.async_config_entry_first_refresh()

    # Favorites should be empty
    assert len(coordinator.favorites) == 0


async def test_coordinator_fetch_once_behavior(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test that interval types and favorites are only fetched once."""
    coordinator = MoodoDataUpdateCoordinator(
        hass,
        mock_moodo_api_client,
        mock_config_entry,
    )

    # First refresh
    await coordinator.async_config_entry_first_refresh()

    # Second refresh
    await coordinator.async_refresh()

    # Should only be called once
    assert mock_moodo_api_client.get_interval_types.call_count == 1
    assert mock_moodo_api_client.get_favorites.call_count == 1
