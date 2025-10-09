"""Support for Moodo fan platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .api import MoodoConnectionError
from .const import BOX_STATUS_OFF, BOX_STATUS_ON, DOMAIN
from .coordinator import MoodoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Moodo uses 0-100 for fan volume
SPEED_RANGE = (1, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Moodo fan platform."""
    coordinator: MoodoDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        MoodoFan(coordinator, device_key)
        for device_key in coordinator.data
    ]

    async_add_entities(entities)


class MoodoFan(CoordinatorEntity[MoodoDataUpdateCoordinator], FanEntity):
    """Representation of a Moodo device as a fan."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._attr_unique_id = f"{device_key}_fan"

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
        return box.get("is_online", False)

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        box = self.coordinator.data.get(self._device_key, {})
        return box.get("box_status") == BOX_STATUS_ON

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.is_on:
            return 0

        box = self.coordinator.data.get(self._device_key, {})
        fan_volume = box.get("fan_volume", 0)

        if fan_volume == 0:
            return 0

        return ranged_value_to_percentage(SPEED_RANGE, fan_volume)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        fan_volume = None
        if percentage is not None:
            fan_volume = int(percentage_to_ranged_value(SPEED_RANGE, percentage))

        try:
            # Optimistically update state
            updates = {"box_status": 1}
            if fan_volume is not None:
                updates["fan_volume"] = fan_volume
            self.coordinator.update_box_data(self._device_key, updates)

            await self.coordinator.client.power_on_box(
                self._device_key, fan_volume=fan_volume
            )
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to turn on Moodo device: %s", err)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        try:
            # Optimistically update state
            self.coordinator.update_box_data(self._device_key, {"box_status": 0})

            await self.coordinator.client.power_off_box(self._device_key)
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to turn off Moodo device: %s", err)
            await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        fan_volume = int(percentage_to_ranged_value(SPEED_RANGE, percentage))

        try:
            # Optimistically update state
            self.coordinator.update_box_data(self._device_key, {"fan_volume": fan_volume})

            await self.coordinator.client.set_fan_volume(self._device_key, fan_volume)
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to set Moodo fan volume: %s", err)
            await self.coordinator.async_request_refresh()
