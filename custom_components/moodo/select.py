"""Support for Moodo select platform."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MoodoConnectionError
from .const import BOX_MODE_DIFFUSER, BOX_MODE_PURIFIER, DOMAIN
from .coordinator import MoodoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MoodoSelectEntityDescription(SelectEntityDescription):
    """Describes Moodo select entity."""

    current_option_fn: Callable[[dict[str, Any]], str | None] | None = None
    options_fn: Callable[[dict[str, Any]], list[str]] | None = None
    select_option_fn: Callable | None = None
    available_fn: Callable[[dict[str, Any]], bool] | None = None


def _get_available_box_modes(box: dict[str, Any]) -> list[str]:
    """Get available box modes based on device capabilities."""
    modes = []
    if box.get("is_diffuser_mode_available", True):  # Default to True if not specified
        modes.append(BOX_MODE_DIFFUSER)
    if box.get("is_purifier_mode_available", False):  # Default to False if not specified
        modes.append(BOX_MODE_PURIFIER)
    # Fallback to both modes if neither flag is present
    if not modes:
        modes = [BOX_MODE_DIFFUSER, BOX_MODE_PURIFIER]
    return modes


SELECT_TYPES: tuple[MoodoSelectEntityDescription, ...] = (
    MoodoSelectEntityDescription(
        key="box_mode",
        translation_key="box_mode",
        name="Mode",
        icon="mdi:air-filter",
        current_option_fn=lambda box: box.get("box_mode"),
        options_fn=_get_available_box_modes,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Moodo select platform."""
    coordinator: MoodoDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[SelectEntity] = []

    for device_key in coordinator.data:
        # Add box mode selector
        entities.append(
            MoodoBoxModeSelect(coordinator, device_key, SELECT_TYPES[0])
        )

        # Add interval type selector if interval types are available
        if coordinator.interval_types:
            entities.append(MoodoIntervalTypeSelect(coordinator, device_key))

        # Add preset selector if favorites are available
        if coordinator.favorites:
            entities.append(MoodoPresetSelect(coordinator, device_key))

    async_add_entities(entities)


class MoodoBoxModeSelect(CoordinatorEntity[MoodoDataUpdateCoordinator], SelectEntity):
    """Representation of a Moodo box mode select."""

    _attr_has_entity_name = True
    entity_description: MoodoSelectEntityDescription

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
        description: MoodoSelectEntityDescription,
    ) -> None:
        """Initialize the select."""
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
        return box.get("is_online", False)

    @property
    def options(self) -> list[str]:
        """Return available options."""
        box = self.coordinator.data.get(self._device_key, {})
        if self.entity_description.options_fn:
            return self.entity_description.options_fn(box)
        return []

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        box = self.coordinator.data.get(self._device_key, {})
        if self.entity_description.current_option_fn:
            return self.entity_description.current_option_fn(box)
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            # Optimistically update state
            self.coordinator.update_box_data(self._device_key, {"box_mode": option})

            await self.coordinator.client.set_box_mode(self._device_key, option)
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to set box mode: %s", err)
            await self.coordinator.async_request_refresh()


class MoodoIntervalTypeSelect(
    CoordinatorEntity[MoodoDataUpdateCoordinator], SelectEntity
):
    """Representation of a Moodo interval type select."""

    _attr_has_entity_name = True
    _attr_translation_key = "interval_type"
    _attr_name = "Interval Type"
    _attr_icon = "mdi:timer-cog-outline"

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._attr_unique_id = f"{device_key}_interval_type"

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
        # Only available if interval mode is enabled
        return box.get("is_online", False) and box.get("interval", False)

    @property
    def options(self) -> list[str]:
        """Return available options."""
        return [
            interval_type.get("keyword", str(interval_type["type"]))
            for interval_type in self.coordinator.interval_types.values()
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        box = self.coordinator.data.get(self._device_key, {})
        interval_type_id = box.get("interval_type")

        if interval_type_id is None:
            return None

        interval_type = self.coordinator.interval_types.get(interval_type_id)
        if interval_type:
            return interval_type.get("keyword", str(interval_type_id))

        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Find interval type ID from keyword
        interval_type_id = None
        for type_id, interval_type in self.coordinator.interval_types.items():
            if interval_type.get("keyword") == option:
                interval_type_id = type_id
                break

        if interval_type_id is None:
            _LOGGER.error("Invalid interval type: %s", option)
            return

        try:
            # Optimistically update state
            self.coordinator.update_box_data(self._device_key, {"interval_type": interval_type_id})

            await self.coordinator.client.enable_interval(
                self._device_key, interval_type=interval_type_id
            )
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to set interval type: %s", err)
            await self.coordinator.async_request_refresh()


class MoodoPresetSelect(CoordinatorEntity[MoodoDataUpdateCoordinator], SelectEntity):
    """Representation of a Moodo preset selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "preset"
    _attr_icon = "mdi:palette"

    def __init__(
        self,
        coordinator: MoodoDataUpdateCoordinator,
        device_key: int,
    ) -> None:
        """Initialize the preset selector."""
        super().__init__(coordinator)
        self._device_key = device_key
        self._attr_unique_id = f"{device_key}_preset"
        # Set static name to ensure consistent entity_id
        self._attr_name = "Preset"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
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
        # Only available if device is online and has matching presets
        available_favorites = self.coordinator.get_available_favorites(self._device_key)
        return box.get("is_online", False) and bool(available_favorites)

    @property
    def options(self) -> list[str]:
        """Return available preset options."""
        # Only show presets that match currently installed capsules
        available_favorites = self.coordinator.get_available_favorites(self._device_key)
        return [fav.get("title", fav["id"]) for fav in available_favorites.values()]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected preset."""
        box = self.coordinator.data.get(self._device_key, {})
        favorite_id = box.get("favorite_id_applied")

        if not favorite_id:
            return None

        # Check if current preset is in available presets
        available_favorites = self.coordinator.get_available_favorites(self._device_key)
        if favorite_id in available_favorites:
            return available_favorites[favorite_id].get("title", favorite_id)

        # If applied preset doesn't match current capsules, show it anyway but it won't be in options
        if favorite_id in self.coordinator.favorites:
            return self.coordinator.favorites[favorite_id].get("title", favorite_id)

        return None

    async def async_select_option(self, option: str) -> None:
        """Apply the selected preset."""
        # Find favorite ID from title in available presets (API uses "favorite" terminology)
        available_favorites = self.coordinator.get_available_favorites(self._device_key)
        favorite_id = None
        favorite_data = None
        for fav_id, fav_data in available_favorites.items():
            if fav_data.get("title") == option:
                favorite_id = fav_id
                favorite_data = fav_data
                break

        if favorite_id is None or favorite_data is None:
            _LOGGER.error("Invalid preset: %s", option)
            return

        try:
            # Prepare optimistic updates
            updates = {"favorite_id_applied": favorite_id}

            # Update capsule intensities from preset settings for immediate UI feedback
            box = self.coordinator.data.get(self._device_key, {})
            current_settings = box.get("settings", [])

            # Map preset settings to current slots by capsule_type_code
            fav_settings = favorite_data.get("settings", [])
            fav_by_capsule = {
                fav_setting.get("capsule_type_code"): fav_setting
                for fav_setting in fav_settings
            }

            # Update each slot's fan settings based on matching capsule type
            updated_settings = []
            for slot_setting in current_settings:
                updated_slot = dict(slot_setting)  # Copy current settings
                capsule_code = slot_setting.get("capsule_type_code")

                if capsule_code in fav_by_capsule:
                    fav_slot = fav_by_capsule[capsule_code]
                    # Update fan speed and active state from preset
                    updated_slot["fan_speed"] = fav_slot.get("fan_speed", 0)
                    updated_slot["fan_active"] = fav_slot.get("fan_active", False)

                updated_settings.append(updated_slot)

            updates["settings"] = updated_settings

            # Optimistically update state
            self.coordinator.update_box_data(self._device_key, updates)

            # Apply preset via API (API uses "favorite" terminology)
            await self.coordinator.client.apply_favorite(favorite_id, self._device_key)
        except MoodoConnectionError as err:
            _LOGGER.error("Failed to apply preset: %s", err)
            await self.coordinator.async_request_refresh()
