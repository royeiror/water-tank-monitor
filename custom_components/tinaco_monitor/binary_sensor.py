"""Binary sensor platform for Tinaco Monitor.

Three binary sensors driven by state-change events from the distance sensor:

  - TinacoLowAlertSensor      — ON when fill % < low_threshold
  - TinacocriticalAlertSensor — ON when fill % < critical_threshold
  - TinacoFullSensor           — ON when fill % >= 95 %
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_CRITICAL_THRESHOLD,
    CONF_DISTANCE_SENSOR,
    CONF_LOW_THRESHOLD,
    CONF_MAX_DISTANCE,
    CONF_MIN_DISTANCE,
    DOMAIN,
    FULL_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config: dict[str, Any] = {**entry.data, **entry.options}
    async_add_entities(
        [
            TinacoLowAlertSensor(hass, entry, config),
            TinacocriticalAlertSensor(hass, entry, config),
            TinacoFullSensor(hass, entry, config),
        ]
    )


# ─── Base ────────────────────────────────────────────────────────────────────


class _TinacoAlertBase(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        config: dict[str, Any],
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._distance_entity: str = config[CONF_DISTANCE_SENSOR]
        self._d_min: float = float(config[CONF_MIN_DISTANCE])
        self._d_max: float = float(config[CONF_MAX_DISTANCE])
        self._low_threshold: float = float(config[CONF_LOW_THRESHOLD])
        self._critical_threshold: float = float(config[CONF_CRITICAL_THRESHOLD])
        self._attr_is_on = False

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Tinaco Monitor",
            "manufacturer": "royeiror",
            "model": "Water Tank Monitor",
            "configuration_url": "https://github.com/royeiror/tinaco-monitor",
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_state_change_event(
                self._hass,
                [self._distance_entity],
                self._on_distance_change,
            )
        )
        state = self._hass.states.get(self._distance_entity)
        if state and state.state not in ("unknown", "unavailable"):
            self._evaluate(state.state)

    @callback
    def _on_distance_change(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        self._evaluate(new_state.state)
        self.async_write_ha_state()

    def _percentage(self, dist_str: str) -> float | None:
        try:
            dist = float(dist_str)
        except (ValueError, TypeError):
            return None
        span = self._d_max - self._d_min
        if span == 0:
            return None
        return max(0.0, min(100.0, (self._d_max - dist) / span * 100.0))

    def _evaluate(self, dist_str: str) -> None:
        raise NotImplementedError


# ─── Concrete binary sensors ─────────────────────────────────────────────────


class TinacoLowAlertSensor(_TinacoAlertBase):
    """ON when fill level is below the user-defined low threshold."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:water-alert"

    def __init__(self, hass, entry, config):
        super().__init__(hass, entry, config)
        self._attr_unique_id = f"{entry.entry_id}_nivel_bajo"
        self._attr_name = "Nivel Bajo"

    def _evaluate(self, dist_str: str) -> None:
        pct = self._percentage(dist_str)
        if pct is not None:
            self._attr_is_on = pct < self._low_threshold


class TinacocriticalAlertSensor(_TinacoAlertBase):
    """ON when fill level is below the user-defined critical threshold."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:water-off"

    def __init__(self, hass, entry, config):
        super().__init__(hass, entry, config)
        self._attr_unique_id = f"{entry.entry_id}_nivel_critico"
        self._attr_name = "Nivel Crítico"

    def _evaluate(self, dist_str: str) -> None:
        pct = self._percentage(dist_str)
        if pct is not None:
            self._attr_is_on = pct < self._critical_threshold


class TinacoFullSensor(_TinacoAlertBase):
    """ON when tank is considered full (>= 95 %)."""

    _attr_device_class = None  # Not a "problem" — informational
    _attr_icon = "mdi:water-check"

    def __init__(self, hass, entry, config):
        super().__init__(hass, entry, config)
        self._attr_unique_id = f"{entry.entry_id}_lleno"
        self._attr_name = "Tinaco Lleno"

    def _evaluate(self, dist_str: str) -> None:
        pct = self._percentage(dist_str)
        if pct is not None:
            self._attr_is_on = pct >= FULL_THRESHOLD
