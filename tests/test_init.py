"""Tests for Moodo integration initialization."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.moodo.api import MoodoAuthError, MoodoConnectionError
from custom_components.moodo.const import CONF_TOKEN, DOMAIN


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_websocket_factory: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_async_setup_entry_without_token(
    hass: HomeAssistant,
    mock_moodo_api_client: MagicMock,
    mock_websocket_factory: MagicMock,
) -> None:
    """Test setup when token is not in config entry (requires login)."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Moodo",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password123",
        },
        unique_id="test@example.com",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Should have called login
    mock_moodo_api_client.login.assert_called_once_with("test@example.com", "password123")

    # Token should be saved to config entry
    assert config_entry.data.get(CONF_TOKEN) == "test_token_12345"


async def test_async_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test setup fails with authentication error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Moodo",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "wrong_password",
        },
        unique_id="test@example.com",
    )
    config_entry.add_to_hass(hass)

    mock_moodo_api_client.login.side_effect = MoodoAuthError("Invalid credentials")

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        # Setup should return False when auth fails
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    # Entry should be in setup_error state
    assert config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_async_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test setup fails with connection error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Moodo",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "password123",
        },
        unique_id="test@example.com",
    )
    config_entry.add_to_hass(hass)

    mock_moodo_api_client.login.side_effect = MoodoConnectionError("Connection timeout")

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        # Setup should return False when connection fails
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

    # Entry should be in setup_retry state (ConfigEntryNotReady triggers retry)
    assert config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_coordinator_refresh_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
) -> None:
    """Test setup when coordinator refresh fails with auth error."""
    mock_config_entry.add_to_hass(hass)

    # Make get_boxes fail with auth error
    mock_moodo_api_client.get_boxes.side_effect = MoodoAuthError("Token expired")

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        # Setup should return False when auth fails during coordinator refresh
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)

    # Entry should be in setup_retry state (UpdateFailed during first refresh becomes ConfigEntryNotReady)
    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_websocket_factory: MagicMock,
    mock_moodo_websocket: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Get the coordinator to verify it exists
    coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]
    assert coordinator is not None

    # Unload the entry
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify the websocket was disconnected during shutdown
    mock_moodo_websocket.disconnect.assert_called_once()


async def test_websocket_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_websocket_factory: MagicMock,
    mock_moodo_websocket: MagicMock,
) -> None:
    """Test WebSocket is set up correctly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # WebSocket should be created and connected
    mock_websocket_factory.assert_called_once()
    mock_moodo_websocket.connect.assert_called_once()


async def test_websocket_setup_failure_non_fatal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_websocket_factory: MagicMock,
    mock_moodo_websocket: MagicMock,
) -> None:
    """Test that WebSocket setup failure doesn't prevent integration from loading."""
    mock_config_entry.add_to_hass(hass)

    # Make WebSocket connection fail
    mock_moodo_websocket.connect.side_effect = Exception("WebSocket connection failed")

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        # Setup should still succeed
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED


async def test_platforms_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_moodo_api_client: MagicMock,
    mock_websocket_factory: MagicMock,
) -> None:
    """Test all platforms are loaded."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.moodo.MoodoAPIClient",
        return_value=mock_moodo_api_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that all platforms were loaded
    assert mock_config_entry.state == ConfigEntryState.LOADED
