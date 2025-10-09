"""Socket.IO client for Moodo real-time updates."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

import socketio

_LOGGER = logging.getLogger(__name__)

SOCKETIO_URL = "https://ws.moodo.co:9090"


class MoodoWebSocket:
    """Moodo Socket.IO client for real-time updates."""

    def __init__(
        self,
        token: str,
        device_ids: list[str],
        update_callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Initialize the Socket.IO client."""
        self._token = token
        self._device_ids = device_ids  # List of device IDs to subscribe to
        self._update_callback = update_callback
        self._sio: socketio.AsyncClient | None = None
        self._running = False

    async def connect(self) -> None:
        """Connect to the Socket.IO server."""
        if self._running:
            return

        self._running = True
        self._sio = socketio.AsyncClient(
            logger=False,
            engineio_logger=False,
            reconnection=True,  # Enable reconnection like homebridge
            reconnection_attempts=0,  # Infinite retries
            reconnection_delay=1,
            reconnection_delay_max=5,
        )

        # Register event handlers
        self._sio.on("connect", self._on_connect)
        self._sio.on("disconnect", self._on_disconnect)
        self._sio.on("connect_error", self._on_connect_error)
        self._sio.on("ws_event", self._on_ws_event)  # Device update events

        try:
            token_preview = self._token[:10] + "..." if len(self._token) > 10 else self._token
            _LOGGER.info("Connecting to Moodo Socket.IO at %s", SOCKETIO_URL)

            # Connect without authentication (will authenticate after connect)
            # Use default transports (polling, then upgrade to websocket) for Socket.IO v2 compatibility
            await self._sio.connect(SOCKETIO_URL)
            _LOGGER.info("Successfully connected to Moodo Socket.IO")
        except Exception as err:
            _LOGGER.error("Failed to connect to Socket.IO: %s", err, exc_info=True)
            self._running = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from the Socket.IO server."""
        self._running = False

        if self._sio and self._sio.connected:
            await self._sio.disconnect()
            _LOGGER.info("Disconnected from Moodo Socket.IO")

        self._sio = None


    async def _on_connect(self) -> None:
        """Handle connection event."""
        _LOGGER.info("Socket.IO connected successfully")

        # Socket.IO v2 connection flow:
        # 1. Wait 1 second
        # 2. Authenticate with token
        # 3. Wait 2 seconds
        # 4. Subscribe to each device ID individually
        try:
            if self._sio:
                _LOGGER.debug("Waiting 1 second before authentication...")
                await asyncio.sleep(1)

                token_preview = self._token[:10] + "..." if len(self._token) > 10 else self._token
                _LOGGER.info("Authenticating with token %s", token_preview)
                await self._sio.emit("authenticate", self._token)

                _LOGGER.debug("Waiting 2 seconds before subscription...")
                await asyncio.sleep(2)

                # Subscribe to each device ID
                for device_id in self._device_ids:
                    _LOGGER.info("Subscribing to device: %s", device_id)
                    await self._sio.emit("subscribe", device_id)

                _LOGGER.info("Authentication and subscription complete - waiting for ws_event updates")
        except Exception as err:
            _LOGGER.error("Failed to authenticate/subscribe: %s", err, exc_info=True)

    async def _on_disconnect(self) -> None:
        """Handle disconnection event."""
        if self._running:
            _LOGGER.warning("Socket.IO disconnected - auto-reconnect will attempt to reconnect")
        else:
            _LOGGER.info("Socket.IO disconnected (intentional)")

    async def _on_connect_error(self, data: Any) -> None:
        """Handle connection error event."""
        _LOGGER.error("Socket.IO connection error: %s", data)

    async def _on_ws_event(self, event_data: Any) -> None:
        """Handle ws_event from Moodo server (device updates)."""
        _LOGGER.debug("Received ws_event: %s", event_data)

        try:
            # Event structure: { type: 'box_config', data: {...box data...}, restful_request_id: string, sent: timestamp }
            if not event_data or not isinstance(event_data, dict):
                return

            # Extract the box data and request ID from the event
            box_data = event_data.get("data")
            request_id = event_data.get("restful_request_id")

            if box_data and self._update_callback:
                await self._update_callback(box_data, request_id)

        except Exception as err:
            _LOGGER.exception("Error handling ws_event: %s", err)
