"""Support for Moodo sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SLOT_IDS
from .coordinator import MoodoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MoodoSensorEntityDescription(SensorEntityDescription):
    """Describes Moodo sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType] | None = None
    available_fn: Callable[[dict[str, Any]], bool] | None = None


SENSOR_TYPES: tuple[MoodoSensorEntityDescription, ...] = (
    MoodoSensorEntityDescription(
        key="battery_level",
        translation_key="battery_level",
        name="Battery Level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda box: box.get("battery_level_percent"),
        available_fn=lambda box: box.get("is_online", False) and box.get("has_battery", False),
    ),
    MoodoSensorEntityDescription(
        key="is_adapter_on",
        translation_key="adapter_status",
        name="Adapter Status",
        icon="mdi:power-plug",
        value_fn=lambda box: "on" if box.get("is_adapter_on") else "off",
    ),
    MoodoSensorEntityDescription(
        key="is_battery_charging",
        translation_key="charging_status",
        name="Charging Status",
        icon="mdi:battery-charging",
        value_fn=lambda box: "charging" if box.get("is_battery_charging") else "not_charging",
        available_fn=lambda box: box.get("is_online", False) and box.get("has_battery", False),
    ),
    MoodoSensorEntityDescription(
        key="favorite_id_applied",
        translation_key="active_preset",
        name="Active Preset",
        icon="mdi:palette",
        value_fn=lambda box: box.get("favorite_id_applied") or "None",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Moodo sensor platform."""
    coordinator: MoodoDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SensorEntity] = []

    for device_key in coordinator.data:
        # Add standard sensors
        for description in SENSOR_TYPES:
            entities.append(MoodoSensor(coordinator, device_key, description))

        # Add capsule type sensors
        for slot_id in SLOT_IDS:
            entities.append(MoodoCapsuleTypeSensor(coordinator, device_key, slot_id))
            entities.append(MoodoCapsuleFragranceSensor(coordinator, device_key, slot_id))

    async_add_entities(entities)


class MoodoSensor(CoordinatorEntity[MoodoDataUpdateCoordinator], SensorEntity):
    """Representation of a Moodo sensor."""

    _attr_has_entity_name = True
    entity_description: MoodoSensorEntityDescription

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
        description: MoodoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
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

        # Use custom availability function if provided
        if self.entity_description.available_fn:
            return self.entity_description.available_fn(box)

        return box.get("is_online", False)

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        box = self.coordinator.data.get(self._device_key, {})

        # Special handling for preset sensor - show title instead of ID
        if self.entity_description.key == "favorite_id_applied":
            favorite_id = box.get("favorite_id_applied")
            if not favorite_id:
                return "None"

            # Look up preset title from coordinator (API uses "favorite" terminology)
            if self.coordinator.favorites and favorite_id in self.coordinator.favorites:
                title = self.coordinator.favorites[favorite_id].get("title")
                if title:
                    return title

            # If presets not loaded yet or preset not found, show ID
            _LOGGER.debug(
                "Preset ID %s not found in presets list (have %d presets)",
                favorite_id,
                len(self.coordinator.favorites) if self.coordinator.favorites else 0,
            )
            return favorite_id

        # Special handling for battery level - if charging and battery shows 0, report 100%
        if self.entity_description.key == "battery_level":
            battery_level = box.get("battery_level_percent", 0)
            is_charging = box.get("is_battery_charging", False)
            # If charging and battery is 0, assume it's fully charged (API quirk)
            if is_charging and battery_level == 0:
                return 100
            return battery_level

        # Special handling for adapter status - if charging, adapter must be on
        if self.entity_description.key == "is_adapter_on":
            is_adapter_on = box.get("is_adapter_on", False)
            is_charging = box.get("is_battery_charging", False)
            # If charging, adapter is definitely on regardless of API value
            if is_charging:
                return "on"
            return "on" if is_adapter_on else "off"

        if self.entity_description.value_fn:
            return self.entity_description.value_fn(box)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        # For preset sensor, include the preset ID (API uses "favorite" terminology)
        if self.entity_description.key == "favorite_id_applied":
            box = self.coordinator.data.get(self._device_key, {})
            favorite_id = box.get("favorite_id_applied")
            if favorite_id:
                return {"preset_id": favorite_id}
        return None


class MoodoCapsuleTypeSensor(
    CoordinatorEntity[MoodoDataUpdateCoordinator], SensorEntity
):
    """Representation of a Moodo capsule type sensor."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:flask"

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
        slot_id: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._slot_id = slot_id
        self._attr_unique_id = f"{device_key}_capsule_{slot_id}_type"

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
    def name(self) -> str:
        """Return the name of the entity."""
        return f"Capsule {self._slot_id + 1} Type"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        box = self.coordinator.data.get(self._device_key)
        if box is None:
            return False
        return box.get("is_online", False)

    @property
    def native_value(self) -> str | None:
        """Return the capsule title."""
        box = self.coordinator.data.get(self._device_key, {})
        settings = box.get("settings", [])

        # Find the slot settings
        slot_setting = next(
            (s for s in settings if s.get("slot_id") == self._slot_id), None
        )

        if slot_setting:
            capsule_info = slot_setting.get("capsule_info", {})
            title = capsule_info.get("title")
            if title:
                return title

        return "Empty"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        box = self.coordinator.data.get(self._device_key, {})
        settings = box.get("settings", [])

        # Find the slot settings
        slot_setting = next(
            (s for s in settings if s.get("slot_id") == self._slot_id), None
        )

        if slot_setting:
            capsule_info = slot_setting.get("capsule_info", {})
            attributes = {
                "color": capsule_info.get("color"),
                "is_digital": capsule_info.get("is_digital"),
                "capsule_type_code": slot_setting.get("capsule_type_code"),
                "fan_active": slot_setting.get("fan_active"),
                "slot_manual_usage_percent": slot_setting.get("slot_manual_usage_percent"),
            }

            # Add fragrance_left_percent if available
            fragrance_left = slot_setting.get("fragrance_left_percent")
            if fragrance_left is not None:
                attributes["fragrance_left_percent"] = fragrance_left

            return attributes

        return None


class MoodoCapsuleFragranceSensor(
    CoordinatorEntity[MoodoDataUpdateCoordinator], SensorEntity
):
    """Representation of a Moodo capsule fragrance level sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.BATTERY  # Use battery class for percentage display
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:spray"

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
        slot_id: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._slot_id = slot_id
        self._attr_unique_id = f"{device_key}_capsule_{slot_id}_remaining"
        # Set static name to ensure consistent entity_id
        self._attr_name = f"Capsule {slot_id + 1} Remaining"

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
    def native_value(self) -> int | None:
        """Return the fragrance level percentage."""
        box = self.coordinator.data.get(self._device_key, {})
        settings = box.get("settings", [])

        # Find the slot settings
        slot_setting = next(
            (s for s in settings if s.get("slot_id") == self._slot_id), None
        )

        if slot_setting:
            # Try fragrance_left_percent first (actual remaining fragrance)
            fragrance_left = slot_setting.get("fragrance_left_percent")
            if fragrance_left is not None:
                return int(round(fragrance_left))

            # Fallback to slot_manual_usage_percent (manual usage setting)
            manual_usage = slot_setting.get("slot_manual_usage_percent")
            if manual_usage is not None:
                return int(round(manual_usage))

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        box = self.coordinator.data.get(self._device_key, {})
        settings = box.get("settings", [])

        # Find the slot settings
        slot_setting = next(
            (s for s in settings if s.get("slot_id") == self._slot_id), None
        )

        if slot_setting:
            capsule_info = slot_setting.get("capsule_info", {})
            attrs = {
                "capsule_name": capsule_info.get("title"),
                "capsule_color": capsule_info.get("color"),
                "is_digital": capsule_info.get("is_digital", False),
            }

            # Include both values if available so user knows which is being used
            fragrance_left = slot_setting.get("fragrance_left_percent")
            manual_usage = slot_setting.get("slot_manual_usage_percent")

            if fragrance_left is not None:
                attrs["fragrance_left_percent"] = fragrance_left
                attrs["source"] = "actual_remaining"
            elif manual_usage is not None:
                attrs["slot_manual_usage_percent"] = manual_usage
                attrs["source"] = "manual_setting"

            return attrs

        return None
