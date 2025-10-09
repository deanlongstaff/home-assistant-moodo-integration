"""Support for Moodo number platform."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MoodoConnectionError
from .const import DOMAIN, SLOT_IDS
from .coordinator import MoodoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Moodo number platform."""
    coordinator: MoodoDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        MoodoCapsuleSpeed(coordinator, device_key, slot_id)
        for device_key in coordinator.data
        for slot_id in SLOT_IDS
    ]

    async_add_entities(entities)


class MoodoCapsuleSpeed(CoordinatorEntity[MoodoDataUpdateCoordinator], NumberEntity):
    """Representation of a Moodo capsule fan speed control."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:fan"

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
        slot_id: int,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._slot_id = slot_id
        # Use static unique_id with slot number only
        self._attr_unique_id = f"{device_key}_slot_{slot_id}_intensity"
        # Set static name to ensure entity_id is based on slot number, not capsule name
        self._attr_name = f"Capsule {slot_id + 1} Intensity"

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes including capsule name."""
        box = self.coordinator.data.get(self._device_key, {})
        settings = box.get("settings", [])

        # Find the slot settings
        slot_setting = next(
            (s for s in settings if s.get("slot_id") == self._slot_id), None
        )

        attrs = {"slot_id": self._slot_id}

        if slot_setting:
            capsule_info = slot_setting.get("capsule_info", {})
            if capsule_info:
                attrs["capsule_name"] = capsule_info.get("title")
                attrs["capsule_color"] = capsule_info.get("color")
                attrs["is_digital"] = capsule_info.get("is_digital", False)

        return attrs

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        box = self.coordinator.data.get(self._device_key)
        if box is None:
            return False

        is_online = box.get("is_online", False)
        if not is_online:
            return False

        # Check if this specific capsule's fan slider is movable
        settings = box.get("settings", [])
        slot_setting = next(
            (s for s in settings if s.get("slot_id") == self._slot_id), None
        )

        if slot_setting:
            # Only available if the fan slider is movable for this capsule
            return slot_setting.get("is_fan_slider_movable", True)

        return True  # Default to available if slot not found

    @property
    def native_value(self) -> float | None:
        """Return the current fan speed for this slot."""
        box = self.coordinator.data.get(self._device_key, {})
        settings = box.get("settings", [])

        # Find the slot settings
        slot_setting = next(
            (s for s in settings if s.get("slot_id") == self._slot_id), None
        )

        if slot_setting:
            return slot_setting.get("fan_speed", 0)

        return 0

    async def async_set_native_value(self, value: float) -> None:
        """Set the fan speed for this slot."""
        box = self.coordinator.data.get(self._device_key, {})
        settings = box.get("settings", [])

        # Build slot settings dict from current settings
        slot_settings = {}
        for slot_setting in settings:
            slot_id = slot_setting.get("slot_id")
            if slot_id is not None:
                slot_settings[slot_id] = {
                    "fan_speed": slot_setting.get("fan_speed", 0),
                    "fan_active": slot_setting.get("fan_active", False),
                }

        # Update the specific slot we're controlling
        if self._slot_id not in slot_settings:
            slot_settings[self._slot_id] = {"fan_speed": 0, "fan_active": False}

        slot_settings[self._slot_id]["fan_speed"] = int(value)
        slot_settings[self._slot_id]["fan_active"] = value > 0

        try:
            # Optimistically update the slot setting in coordinator data
            updated_settings = settings.copy()
            for i, slot_setting in enumerate(updated_settings):
                if slot_setting.get("slot_id") == self._slot_id:
                    updated_settings[i] = {**slot_setting, "fan_speed": int(value), "fan_active": value > 0}
                    break
            self.coordinator.update_box_data(self._device_key, {"settings": updated_settings})

            await self.coordinator.client.set_fan_speeds(
                self._device_key, slot_settings
            )
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to set capsule fan speed: %s", err)
            await self.coordinator.async_request_refresh()
