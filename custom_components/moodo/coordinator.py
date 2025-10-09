"""DataUpdateCoordinator for Moodo integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MoodoAPIClient, MoodoAuthError, MoodoConnectionError
from .const import CONF_TOKEN, DOMAIN, UPDATE_INTERVAL
from .websocket import MoodoWebSocket

_LOGGER = logging.getLogger(__name__)


class MoodoDataUpdateCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Class to manage fetching Moodo data from the API."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: MoodoAPIClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.config_entry = config_entry
        self.interval_types: dict[int, dict[str, Any]] = {}
        self.favorites: dict[str, dict[str, Any]] = {}  # favorite_id -> favorite data
        self.websocket: MoodoWebSocket | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    async def _async_setup_websocket(self) -> None:
        """Set up WebSocket connection for real-time updates."""
        token = self.config_entry.data.get(CONF_TOKEN)
        if not token:
            _LOGGER.warning("No token available for WebSocket connection")
            return

        # Get device IDs from current data to subscribe to
        if not self.data:
            _LOGGER.warning("No device data available yet for WebSocket subscription")
            return

        device_ids = [box_data.get("id") for box_data in self.data.values() if box_data.get("id")]
        if not device_ids:
            _LOGGER.warning("No device IDs found for WebSocket subscription")
            return

        _LOGGER.info("Setting up WebSocket connection for devices: %s", device_ids)
        self.websocket = MoodoWebSocket(token, device_ids, self._handle_websocket_message)

        try:
            await self.websocket.connect()
            _LOGGER.info("WebSocket connection established")
        except Exception as err:
            _LOGGER.warning(
                "Failed to connect WebSocket (will rely on polling): %s", err
            )
            # WebSocket failure is non-fatal, polling will continue to work
            self.websocket = None

    async def _handle_websocket_message(
        self, box_data: dict[str, Any], request_id: str | None = None
    ) -> None:
        """Handle incoming WebSocket message (box update)."""
        try:
            # Check if this update was triggered by our own API call
            if request_id and self.client.should_ignore_websocket_event(request_id):
                _LOGGER.debug(
                    "Ignoring WebSocket update for request_id=%s (our own action)", request_id
                )
                return

            device_key = box_data.get("device_key")
            if device_key and self.data:
                # Update the specific box in our data
                self.data[device_key] = box_data
                self.async_set_updated_data(self.data)
                _LOGGER.debug("Updated box %s from WebSocket", device_key)
        except Exception as err:
            _LOGGER.error("Error handling WebSocket message: %s", err)

    def update_box_data(self, device_key: int, updates: dict[str, Any]) -> None:
        """Optimistically update box data in coordinator (for immediate UI feedback)."""
        if self.data and device_key in self.data:
            self.data[device_key].update(updates)
            self.async_set_updated_data(self.data)
            _LOGGER.debug("Optimistically updated box %s: %s", device_key, updates)

    def get_available_favorites(self, device_key: int) -> dict[str, dict[str, Any]]:
        """Get favorites that match the currently installed capsules for a device."""
        if not self.data or device_key not in self.data:
            return {}

        box = self.data[device_key]
        settings = box.get("settings", [])

        # Get currently installed capsule type codes (sorted set for comparison)
        installed_capsules = sorted([
            setting.get("capsule_type_code")
            for setting in settings
            if setting.get("capsule_type_code") is not None
        ])

        # Filter favorites to only those matching all installed capsules
        available_favorites = {}
        for fav_id, favorite in self.favorites.items():
            fav_settings = favorite.get("settings", [])

            # Get required capsule type codes from favorite (sorted set for comparison)
            required_capsules = sorted([
                fav_setting.get("capsule_type_code")
                for fav_setting in fav_settings
                if fav_setting.get("capsule_type_code") is not None
            ])

            # Favorite matches if all required capsules are installed (regardless of slot position)
            if required_capsules == installed_capsules:
                available_favorites[fav_id] = favorite

        _LOGGER.debug(
            "Device %s has %d available favorites (out of %d total) for capsules %s",
            device_key,
            len(available_favorites),
            len(self.favorites),
            installed_capsules,
        )
        return available_favorites

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and close WebSocket."""
        if self.websocket:
            await self.websocket.disconnect()
            self.websocket = None

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch data from API endpoint."""
        try:
            boxes = await self.client.get_boxes()

            # Fetch interval types once if not already loaded
            if not self.interval_types:
                try:
                    interval_types_list = await self.client.get_interval_types()
                    self.interval_types = {
                        interval_type["type"]: interval_type
                        for interval_type in interval_types_list
                    }
                except Exception as err:
                    _LOGGER.warning("Failed to fetch interval types: %s", err)

            # Fetch favorites once if not already loaded (list rarely changes)
            if not self.favorites:
                try:
                    favorites_list = await self.client.get_favorites()
                    self.favorites = {
                        favorite["id"]: favorite
                        for favorite in favorites_list
                    }
                    _LOGGER.info("Loaded %d favorites", len(self.favorites))
                except Exception as err:
                    _LOGGER.warning("Failed to fetch favorites: %s", err)

            # Index boxes by device_key for easy lookup
            return {box["device_key"]: box for box in boxes}

        except MoodoAuthError as err:
            # Auth error should trigger reauth flow
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except MoodoConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
