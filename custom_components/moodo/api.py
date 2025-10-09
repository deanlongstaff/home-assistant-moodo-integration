"""Moodo API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any
import uuid

import aiohttp

from .const import API_BASE_URL, API_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class MoodoAuthError(Exception):
    """Exception raised for authentication errors."""


class MoodoConnectionError(Exception):
    """Exception raised for connection errors."""


class MoodoAPIClient:
    """Moodo API client."""

    def __init__(self, session: aiohttp.ClientSession, token: str | None = None) -> None:
        """Initialize the API client."""
        self._session = session
        self._token = token
        self._base_url = API_BASE_URL
        self._recent_request_ids: set[str] = set()  # Track recent request IDs to ignore in WebSocket

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["token"] = self._token
        return headers

    def should_ignore_websocket_event(self, request_id: str | None) -> bool:
        """Check if a WebSocket event should be ignored based on request ID."""
        if request_id and request_id in self._recent_request_ids:
            self._recent_request_ids.discard(request_id)  # Remove after checking
            return True
        return False

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | None = None,
        add_request_id: bool = False,
    ) -> dict[str, Any]:
        """Make an API request."""
        url = f"{self._base_url}{endpoint}"
        headers = self._get_headers()

        # Add unique request ID for WebSocket filtering if requested
        if add_request_id:
            if data is None:
                data = {}
            request_id = str(uuid.uuid4())
            data["restful_request_id"] = request_id
            self._recent_request_ids.add(request_id)
            # Limit set size to prevent memory growth
            if len(self._recent_request_ids) > 100:
                self._recent_request_ids.pop()

        try:
            async with asyncio.timeout(API_TIMEOUT):
                async with self._session.request(
                    method, url, json=data, headers=headers
                ) as response:
                    # Authentication errors
                    if response.status in (401, 403):
                        raise MoodoAuthError("Authentication failed")

                    # Handle error responses
                    if response.status >= 400:
                        try:
                            error_data = await response.json()
                            error_message = error_data.get("error", "Unknown error")
                        except Exception:
                            error_message = f"HTTP {response.status}"

                        # Check if this is an authentication error based on message
                        if any(keyword in error_message.lower() for keyword in ["credentials", "password", "email", "unauthorized", "authentication", "login"]):
                            raise MoodoAuthError(error_message)

                        raise MoodoConnectionError(f"API error: {error_message}")

                    return await response.json()
        except MoodoAuthError:
            raise  # Re-raise auth errors as-is
        except MoodoConnectionError:
            raise  # Re-raise connection errors as-is
        except asyncio.TimeoutError as err:
            raise MoodoConnectionError("Request timeout") from err
        except aiohttp.ClientError as err:
            raise MoodoConnectionError(f"Connection error: {err}") from err

    async def login(self, email: str, password: str) -> str:
        """Login and get authentication token."""
        data = {"email": email, "password": password}
        response = await self._request("POST", "/login", data)
        token = response.get("token")
        if not token:
            raise MoodoAuthError("No token in response")
        self._token = token
        return token

    async def get_boxes(self) -> list[dict[str, Any]]:
        """Get all Moodo boxes for the current user."""
        response = await self._request("GET", "/boxes")
        return response.get("boxes", [])

    async def get_box(self, device_key: int) -> dict[str, Any]:
        """Get a single Moodo box."""
        response = await self._request("GET", f"/boxes/{device_key}")
        return response.get("box", {})

    async def power_on_box(
        self,
        device_key: int,
        fan_volume: int | None = None,
        duration_minutes: int | None = None,
        favorite_id: str | None = None,
    ) -> dict[str, Any]:
        """Power on a Moodo box."""
        data: dict[str, Any] = {}
        if fan_volume is not None:
            data["fan_volume"] = fan_volume
        if duration_minutes is not None:
            data["duration_minutes"] = duration_minutes
        if favorite_id is not None:
            data["favorite_id"] = favorite_id

        response = await self._request(
            "POST", f"/boxes/{device_key}", data if data else None, add_request_id=True
        )
        return response.get("box", {})

    async def power_off_box(self, device_key: int) -> dict[str, Any]:
        """Power off a Moodo box."""
        response = await self._request("DELETE", f"/boxes/{device_key}")
        return response.get("box", {})

    async def set_fan_volume(self, device_key: int, fan_volume: int) -> dict[str, Any]:
        """Set the main intensity (fan volume) for a Moodo box."""
        data = {"fan_volume": fan_volume}
        response = await self._request(
            "POST", f"/intensity/{device_key}", data, add_request_id=True
        )
        return response.get("box", {})

    async def set_box_mode(self, device_key: int, box_mode: str) -> dict[str, Any]:
        """Switch box mode (diffuser/purifier)."""
        data = {"box_mode": box_mode}
        response = await self._request(
            "POST", f"/mode/{device_key}", data, add_request_id=True
        )
        return response.get("box", {})

    async def enable_shuffle(self, device_key: int) -> dict[str, Any]:
        """Enable shuffle mode."""
        response = await self._request("POST", f"/shuffle/{device_key}")
        return response.get("box", {})

    async def disable_shuffle(self, device_key: int) -> dict[str, Any]:
        """Disable shuffle mode."""
        response = await self._request("DELETE", f"/shuffle/{device_key}")
        return response.get("box", {})

    async def enable_interval(
        self, device_key: int, interval_type: int | None = None
    ) -> dict[str, Any]:
        """Enable interval mode."""
        data = {}
        if interval_type is not None:
            data["interval_type"] = interval_type
        response = await self._request(
            "POST", f"/interval/{device_key}", data if data else None, add_request_id=True
        )
        return response.get("box", {})

    async def disable_interval(self, device_key: int) -> dict[str, Any]:
        """Disable interval mode."""
        response = await self._request("DELETE", f"/interval/{device_key}")
        return response.get("box", {})

    async def get_interval_types(self) -> list[dict[str, Any]]:
        """Get available interval types."""
        response = await self._request("GET", "/interval")
        return response.get("interval_types", [])

    async def set_fan_speeds(
        self,
        device_key: int,
        slot_settings: dict[int, dict[str, Any]],
        box_status: int | None = None,
        duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Set individual fan speeds for all slots."""
        data: dict[str, Any] = {
            "device_key": device_key,
            "settings_slot0": slot_settings.get(0, {"fan_speed": 0, "fan_active": False}),
            "settings_slot1": slot_settings.get(1, {"fan_speed": 0, "fan_active": False}),
            "settings_slot2": slot_settings.get(2, {"fan_speed": 0, "fan_active": False}),
            "settings_slot3": slot_settings.get(3, {"fan_speed": 0, "fan_active": False}),
        }
        if box_status is not None:
            data["box_status"] = box_status
        if duration_seconds is not None:
            data["duration_seconds"] = duration_seconds

        response = await self._request("PUT", "/boxes", data, add_request_id=True)
        return response.get("box", {})

    async def get_favorites(self) -> list[dict[str, Any]]:
        """Get all favorites."""
        response = await self._request("GET", "/favorites")
        return response.get("favorites", [])

    async def apply_favorite(
        self,
        favorite_id: str,
        device_key: int,
        fan_volume: int | None = None,
        duration_minutes: int | None = None,
    ) -> dict[str, Any]:
        """Apply a favorite to a device."""
        data: dict[str, Any] = {
            "favorite_id": favorite_id,
            "device_key": device_key,
        }
        if fan_volume is not None:
            data["fan_volume"] = fan_volume
        if duration_minutes is not None:
            data["duration_minutes"] = duration_minutes

        response = await self._request("PATCH", "/favorites", data, add_request_id=True)
        return response.get("box", {})
