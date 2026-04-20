"""Binary sensor platform for Water Tank Monitor.

Two binary sensors driven by the analytics engine:
  - WaterTankSupplyActiveSensor — ON when confirmed supply > 1 min
  - WaterTankLeakSensor         — ON when sustained small drop detected
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SIGNAL_ANALYTICS_UPDATE,
)
from .analytics import WaterTankAnalytics

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config: dict[str, Any] = {**entry.data, **entry.options}
    analytics = hass.data[DOMAIN][entry.entry_id]["analytics"]
    
    async_add_entities(
        [
            WaterTankSupplyActiveSensor(hass, entry, config, analytics),
            WaterTankLeakSensor(hass, entry, config, analytics),
        ]
    )


class WaterTankSupplyActiveSensor(BinarySensorEntity):
    """Reflects whether water is currently flowing into the tank (confirmed)."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_icon = "mdi:water-plus-variant"

    def __init__(self, hass, entry, config, analytics):
        self._hass = hass
        self._entry = entry
        self._analytics = analytics
        self._attr_unique_id = f"{entry.entry_id}_supply_active"
        self._attr_name = "Supply Active"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Water Tank Monitor",
        }

    @property
    def is_on(self) -> bool:
        return self._analytics.is_filling

    async def async_added_to_hass(self) -> None:
        """Subscribe to analytics updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_ANALYTICS_UPDATE}_{self._entry.entry_id}",
                self.async_write_ha_state,
            )
        )


class WaterTankLeakSensor(BinarySensorEntity):
    """ON when a potential leak is detected."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.MOISTURE
    _attr_icon = "mdi:water-leak"

    def __init__(self, hass, entry, config, analytics):
        self._hass = hass
        self._entry = entry
        self._analytics = analytics
        self._attr_unique_id = f"{entry.entry_id}_leak_detected"
        self._attr_name = "Leak Detected"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Water Tank Monitor",
        }

    @property
    def is_on(self) -> bool:
        return self._analytics.is_leaking

    async def async_added_to_hass(self) -> None:
        """Subscribe to analytics updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_ANALYTICS_UPDATE}_{self._entry.entry_id}",
                self.async_write_ha_state,
            )
        )
