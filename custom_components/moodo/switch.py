"""Support for Moodo switch platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MoodoConnectionError
from .const import DOMAIN
from .coordinator import MoodoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MoodoSwitchEntityDescription(SwitchEntityDescription):
    """Describes Moodo switch entity."""

    is_on_fn: Callable[[dict[str, Any]], bool] | None = None
    turn_on_fn: Callable | None = None
    turn_off_fn: Callable | None = None


SWITCH_TYPES: tuple[MoodoSwitchEntityDescription, ...] = (
    MoodoSwitchEntityDescription(
        key="shuffle",
        translation_key="shuffle",
        name="Shuffle",
        icon="mdi:shuffle-variant",
        is_on_fn=lambda box: box.get("shuffle", False),
    ),
    MoodoSwitchEntityDescription(
        key="interval",
        translation_key="interval",
        name="Interval",
        icon="mdi:timer-outline",
        is_on_fn=lambda box: box.get("interval", False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Moodo switch platform."""
    coordinator: MoodoDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        MoodoSwitch(coordinator, device_key, description)
        for device_key in coordinator.data
        for description in SWITCH_TYPES
    ]

    async_add_entities(entities)


class MoodoSwitch(CoordinatorEntity[MoodoDataUpdateCoordinator], SwitchEntity):
    """Representation of a Moodo switch."""

    _attr_has_entity_name = True
    entity_description: MoodoSwitchEntityDescription

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
        description: MoodoSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_key = device_key
        self._attr_unique_id = f"{device_key}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this Moodo device."""
        box = self.coordinator.data.get(self._device_key, {})

        # Include both string ID and numeric device_key as identifiers
        identifiers = {(DOMAIN, self._device_key)}
        box_id = box.get("id")
        if box_id:
            identifiers.add((DOMAIN, box_id))

        return {
            "identifiers": identifiers,
            "name": box.get("name", f"Moodo {self._device_key}"),
            "manufacturer": "Moodo",
            "model": f"Box v{box.get('box_version', 'Unknown')}",
            "sw_version": str(box.get("box_version", "")),
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        box = self.coordinator.data.get(self._device_key)
        if box is None:
            return False

        is_online = box.get("is_online", False)

        # For interval switch, check can_interval_turn_on (but default to True if field missing)
        # Note: API may set this to False when certain conditions aren't met (e.g., specific capsule config)
        if self.entity_description.key == "interval":
            # Make available even if can't turn on, so user can see why it's disabled
            return is_online

        return is_online

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        box = self.coordinator.data.get(self._device_key, {})
        if self.entity_description.is_on_fn:
            return self.entity_description.is_on_fn(box)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        box = self.coordinator.data.get(self._device_key, {})
        attrs = {}

        # For interval switch, show if it can be turned on
        if self.entity_description.key == "interval":
            can_turn_on = box.get("can_interval_turn_on", True)
            attrs["can_turn_on"] = can_turn_on
            if not can_turn_on:
                attrs["note"] = "Interval mode unavailable for current capsule configuration"

        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            # Optimistically update state immediately for responsive UI
            self.coordinator.update_box_data(self._device_key, {self.entity_description.key: True})

            if self.entity_description.key == "shuffle":
                await self.coordinator.client.enable_shuffle(self._device_key)
            elif self.entity_description.key == "interval":
                await self.coordinator.client.enable_interval(self._device_key)

            # WebSocket or polling will update with actual state
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to turn on %s: %s", self.entity_description.key, err)
            # Revert optimistic update on error
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            # Optimistically update state immediately for responsive UI
            self.coordinator.update_box_data(self._device_key, {self.entity_description.key: False})

            if self.entity_description.key == "shuffle":
                await self.coordinator.client.disable_shuffle(self._device_key)
            elif self.entity_description.key == "interval":
                await self.coordinator.client.disable_interval(self._device_key)

            # WebSocket or polling will update with actual state
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to turn off %s: %s", self.entity_description.key, err)
            # Revert optimistic update on error
            await self.coordinator.async_request_refresh()
