"""The Moodo integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MoodoAPIClient, MoodoAuthError, MoodoConnectionError
from .const import CONF_TOKEN, DOMAIN, PLATFORMS
from .coordinator import MoodoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Moodo from a config entry."""
    session = async_get_clientsession(hass)

    # Get token from config entry, or attempt login if not present
    token = entry.data.get(CONF_TOKEN)

    if not token:
        # Need to login first
        email = entry.data.get(CONF_EMAIL)
        password = entry.data.get(CONF_PASSWORD)

        if not email or not password:
            raise ConfigEntryAuthFailed("Missing email or password")

        client = MoodoAPIClient(session)
        try:
            token = await client.login(email, password)
            # Update config entry with token
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_TOKEN: token},
            )
        except MoodoAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except MoodoConnectionError as err:
            raise ConfigEntryNotReady(f"Connection failed: {err}") from err

    # Initialize API client with token
    client = MoodoAPIClient(session, token)

    # Create coordinator
    coordinator = MoodoDataUpdateCoordinator(hass, client, entry)

    # Fetch initial data
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        # If auth fails, clear token and raise for reauth
        hass.config_entries.async_update_entry(
            entry,
            data={k: v for k, v in entry.data.items() if k != CONF_TOKEN},
        )
        raise

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up WebSocket for real-time updates
    await coordinator._async_setup_websocket()

    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Shutdown WebSocket connection
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_shutdown()

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
