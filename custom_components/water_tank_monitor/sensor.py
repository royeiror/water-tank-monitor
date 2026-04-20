"""Sensor platform for Water Tank Monitor.

Creates three sensor entities driven by state-change events from the configured
distance sensor (no polling):

  - WaterTankPercentageSensor — fill percentage (0–100 %)
  - WaterTankVolumeSensor      — volume in liters
  - WaterTankFillRateSensor    — fill/drain rate in L/h (rolling window)
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_DISTANCE_SENSOR,
    CONF_MAX_DISTANCE,
    CONF_MIN_DISTANCE,
    CONF_TANK_CAPACITY,
    DOMAIN,
    FILL_RATE_WINDOW,
    SIGNAL_RESET_BOUNDS,
    SIGNAL_ANALYTICS_UPDATE,
    CONF_FILL_RATE_UNIT,
    CONF_LOW_THRESHOLD,
    CONF_CRITICAL_THRESHOLD,
    STATUS_CRITICAL,
    STATUS_LOW,
    STATUS_NORMAL,
    STATUS_FULL,
    UNIT_L_H,
    UNIT_L_M,
    UNIT_L_S,
    UNIT_GAL_H,
    UNIT_GAL_M,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    config: dict[str, Any] = {**entry.data, **entry.options}
    analytics = hass.data[DOMAIN][entry.entry_id]["analytics"]

    async_add_entities(
        [
            WaterTankStatusSensor(hass, entry, config, analytics),
            WaterTankPercentageSensor(hass, entry, config, analytics),
            WaterTankVolumeSensor(hass, entry, config, analytics),
            WaterTankFillRateSensor(hass, entry, config, analytics),
            WaterTankRawDistanceSensor(hass, entry, config),
            WaterTankDailySupplySensor(hass, entry, config, analytics),
            WaterTankDailyConsumptionSensor(hass, entry, config, analytics),
            WaterTankTypicalSupplySensor(hass, entry, config, analytics),
        ]
    )


# ─── Shared base ─────────────────────────────────────────────────────────────


class _WaterTankBaseSensor(SensorEntity):
    """Base class: listens to a distance entity and computes derived values."""

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
        self._capacity: float = float(config[CONF_TANK_CAPACITY])
        self._analytics: WaterTankAnalytics = config.get("analytics")

        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Water Tank Monitor",
            "manufacturer": "royeiror",
            "model": "Water Tank Monitor",
            "configuration_url": "https://github.com/royeiror/water-tank-monitor",
        }

    async def async_added_to_hass(self) -> None:
        """Subscribe to distance sensor state changes."""
        self.async_on_remove(
            async_track_state_change_event(
                self._hass,
                [self._distance_entity],
                self._on_distance_change,
            )
        )
        state = self._hass.states.get(self._distance_entity)
        if state and state.state not in ("unknown", "unavailable"):
            self._process(state.state)

    @callback
    def _on_distance_change(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return
        self._process(new_state.state)
        self.async_write_ha_state()

    def _percentage(self, dist_str: str) -> float | None:
        """Return fill % from a raw distance string, or None on bad input."""
        try:
            dist = float(dist_str)
        except (ValueError, TypeError):
            return None
        span = self._d_max - self._d_min
        if span == 0:
            return None
        pct = (self._d_max - dist) / span * 100.0
        return max(0.0, min(100.0, pct))

    def _process(self, dist_str: str) -> None:
        """Override in subclasses to process raw distance."""
        pass


# ─── Concrete sensors ─────────────────────────────────────────────────────────


class WaterTankPercentageSensor(_WaterTankBaseSensor):
    """Fill percentage — 0 % (empty) → 100 % (full)."""

    _attr_native_unit_of_measurement = "%"
    _attr_icon = "mdi:water-percent"
    _attr_suggested_display_precision = 1
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, analytics):
        super().__init__(hass, entry, config)
        self._analytics = analytics
        self._attr_unique_id = f"{entry.entry_id}_percentage"
        self._attr_name = "Fill Percentage"

    async def async_added_to_hass(self) -> None:
        """Subscribe to analytics updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_ANALYTICS_UPDATE}_{self._entry.entry_id}",
                self._on_analytics_update,
            )
        )

    @callback
    def _on_analytics_update(self) -> None:
        """Update value from analytics when smoothed volume changes."""
        vol = self._analytics.smoothed_volume
        if vol is None:
            self._attr_native_value = None
        else:
            pct = (vol / self._capacity) * 100.0 if self._capacity > 0 else 0
            self._attr_native_value = round(max(0.0, min(100.0, pct)), 1)
        self.async_write_ha_state()

    def _process(self, dist_str: str) -> None:
        pass


class WaterTankVolumeSensor(_WaterTankBaseSensor):
    """Current water volume in liters."""

    _attr_native_unit_of_measurement = "L"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_icon = "mdi:water"
    _attr_suggested_display_precision = 0
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, analytics):
        super().__init__(hass, entry, config)
        self._analytics = analytics
        self._attr_unique_id = f"{entry.entry_id}_volume"
        self._attr_name = "Water Volume"

    async def async_added_to_hass(self) -> None:
        """Subscribe to analytics updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_ANALYTICS_UPDATE}_{self._entry.entry_id}",
                self._on_analytics_update,
            )
        )

    @callback
    def _on_analytics_update(self) -> None:
        """Update value from analytics when smoothed volume changes."""
        self._attr_native_value = self._analytics.smoothed_volume
        self.async_write_ha_state()

    def _process(self, dist_str: str) -> None:
        pass


class WaterTankFillRateSensor(_WaterTankBaseSensor):
    """Rolling fill/drain rate in L/h.

    Positive → filling, negative → draining, ~0 → static.
    Computed over the last FILL_RATE_WINDOW distance readings.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config, analytics):
        super().__init__(hass, entry, config)
        self._analytics = analytics
        self._unit = entry.options.get(CONF_FILL_RATE_UNIT, UNIT_L_H)
        self._attr_unique_id = f"{entry.entry_id}_fill_rate"
        self._attr_name = "Fill Rate"
        self._attr_native_unit_of_measurement = self._unit
        self._readings: deque[tuple[datetime, float]] = deque(maxlen=FILL_RATE_WINDOW)

    def _process(self, dist_str: str) -> None:
        pct = self._percentage(dist_str)
        if pct is None:
            return
        volume = pct / 100.0 * self._capacity
        now = datetime.now(timezone.utc)
        self._readings.append((now, volume))

        if len(self._readings) < 2:
            self._attr_native_value = 0.0
            return

        t0, v0 = self._readings[0]
        t1, v1 = self._readings[-1]
        dt_hours = (t1 - t0).total_seconds() / 3600.0
        if dt_hours < 1e-6:
            self._attr_native_value = 0.0
            return

        val_l_h = (v1 - v0) / dt_hours
        
        # Convert to selected unit
        if self._unit == UNIT_L_M:
            val = val_l_h / 60.0
        elif self._unit == UNIT_L_S:
            val = val_l_h / 3600.0
        elif self._unit == UNIT_GAL_H:
            val = val_l_h * 0.264172
        elif self._unit == UNIT_GAL_M:
            val = (val_l_h * 0.264172) / 60.0
        else: # UNIT_L_H
            val = val_l_h

        self._attr_native_value = round(val, 2)
        
        # Feed analytics with L/h for internal consistency
        if self._analytics:
            self._analytics.process_reading(v1, val_l_h)


class WaterTankRawDistanceSensor(_WaterTankBaseSensor, RestoreSensor):
    """Tracks the current raw distance and maintains the record range seen."""

    _attr_icon = "mdi:ruler"
    _attr_native_unit_of_measurement = "m"
    _attr_suggested_display_precision = 3
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass, entry, config):
        super().__init__(hass, entry, config)
        self._attr_unique_id = f"{entry.entry_id}_raw_distance"
        self._attr_name = "Raw Distance"
        self._attr_native_value = None
        self._lowest_seen = None
        self._highest_seen = None

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_native_value = last_state.state if last_state.state not in ("unknown", "unavailable") else None
            attrs = last_state.attributes
            self._lowest_seen = attrs.get("lowest_seen")
            self._highest_seen = attrs.get("highest_seen")

        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_RESET_BOUNDS}_{self._entry.entry_id}",
                self._reset_bounds,
            )
        )

    @callback
    def _reset_bounds(self) -> None:
        self._lowest_seen = None
        self._highest_seen = None
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "lowest_seen": self._lowest_seen,
            "highest_seen": self._highest_seen,
        }

    def _process(self, dist_str: str) -> None:
        try:
            val = float(dist_str)
        except (ValueError, TypeError):
            return

        self._attr_native_value = val

        if self._lowest_seen is None or val < self._lowest_seen:
            self._lowest_seen = val
        if self._highest_seen is None or val > self._highest_seen:
            self._highest_seen = val


class WaterTankDailySupplySensor(_WaterTankBaseSensor):
    """Tracks total water received today."""

    _attr_icon = "mdi:tray-arrow-down"
    _attr_native_unit_of_measurement = "L"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hass, entry, config, analytics):
        super().__init__(hass, entry, config)
        self._analytics = analytics
        self._attr_unique_id = f"{entry.entry_id}_daily_supply"
        self._attr_name = "Daily Water Received"

    async def async_added_to_hass(self) -> None:
        """Subscribe to analytics updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_ANALYTICS_UPDATE}_{self._entry.entry_id}",
                self.async_write_ha_state,
            )
        )

    @property
    def native_value(self) -> float:
        return round(self._analytics.daily_supply_total, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._analytics.last_supply_stats


class WaterTankDailyConsumptionSensor(_WaterTankBaseSensor):
    """Tracks total water consumed today. Compatible with Energy Dashboard."""

    _attr_icon = "mdi:water-minus"
    _attr_native_unit_of_measurement = "L"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, hass, entry, config, analytics):
        super().__init__(hass, entry, config)
        self._analytics = analytics
        self._attr_unique_id = f"{entry.entry_id}_daily_consumption"
        self._attr_name = "Daily Water Consumed"

    async def async_added_to_hass(self) -> None:
        """Subscribe to analytics updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_ANALYTICS_UPDATE}_{self._entry.entry_id}",
                self.async_write_ha_state,
            )
        )

    @property
    def native_value(self) -> float:
        return round(self._analytics.daily_consumption_total, 1)


class WaterTankStatusSensor(_WaterTankBaseSensor):
    """Consolidated status sensor: Critical, Low, Normal, Full."""

    _attr_icon = "mdi:water-gauge"

    def __init__(self, hass, entry, config, analytics):
        super().__init__(hass, entry, config)
        self._analytics = analytics
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_name = "Tank Status"
        self._low_threshold = config.get(CONF_LOW_THRESHOLD, 20)
        self._crit_threshold = config.get(CONF_CRITICAL_THRESHOLD, 10)

    async def async_added_to_hass(self) -> None:
        """Subscribe to analytics updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_ANALYTICS_UPDATE}_{self._entry.entry_id}",
                self._on_analytics_update,
            )
        )

    @callback
    def _on_analytics_update(self) -> None:
        """Update state based on percentage."""
        vol = self._analytics.smoothed_volume
        if vol is None:
            self._attr_native_value = None
        else:
            pct = (vol / self._capacity) * 100.0 if self._capacity > 0 else 0
            if pct >= 95.0:
                self._attr_native_value = STATUS_FULL
            elif pct <= self._crit_threshold:
                self._attr_native_value = STATUS_CRITICAL
            elif pct <= self._low_threshold:
                self._attr_native_value = STATUS_LOW
            else:
                self._attr_native_value = STATUS_NORMAL
        self.async_write_ha_state()

    def _process(self, dist_str: str) -> None:
        pass


class WaterTankTypicalSupplySensor(_WaterTankBaseSensor):
    """Shows discovered supply windows based on history."""

    _attr_icon = "mdi:clock-check"
    _attr_native_unit_of_measurement = None

    def __init__(self, hass, entry, config, analytics):
        super().__init__(hass, entry, config)
        self._analytics = analytics
        self._attr_unique_id = f"{entry.entry_id}_typical_supply"
        self._attr_name = "Typical Supply Windows"

    async def async_added_to_hass(self) -> None:
        """Subscribe to analytics updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{SIGNAL_ANALYTICS_UPDATE}_{self._entry.entry_id}",
                self.async_write_ha_state,
            )
        )

    @property
    def native_value(self) -> str | None:
        if not self._analytics.typical_supply_times:
            return "Discovery in progress..."
        
        # Sort and group times (simplified: just show them)
        times = sorted(self._analytics.typical_supply_times)
        return ", ".join([t.strftime("%H:%M") for t in times[:3]]) + ("..." if len(times) > 3 else "")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "all_recorded_times": [t.isoformat() for t in self._analytics.typical_supply_times]
        }
