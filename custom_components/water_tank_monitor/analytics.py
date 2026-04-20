"""Intelligent analytics for Water Tank Monitor.

Tracks supply events, identifies consumption patterns (disaggregation),
and discovers typical supply windows based on historical data.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_DETECTION_THRESHOLD,
    CONF_TANK_CAPACITY,
    DEFAULT_DETECTION_THRESHOLD,
    DRAIN_CAT_FLUSH,
    DRAIN_CAT_LAUNDRY,
    DRAIN_CAT_OTHER,
    DRAIN_CAT_SHOWER,
    EVENT_TYPE_DRAIN,
    EVENT_TYPE_SUPPLY,
    SIGNAL_ANALYTICS_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

# Heuristics for disaggregation
# (assuming 700L tank, area approx 0.7m2)
VOL_FLUSH_MIN = 3.0
VOL_FLUSH_MAX = 12.0
VOL_SHOWER_MIN = 25.0
VOL_SHOWER_MAX = 80.0
VOL_LAUNDRY_MIN = 35.0  # Usually multiple cycles


class WaterTankAnalytics:
    """Manages state machine and event detection for a water tank."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.threshold = entry.options.get(CONF_DETECTION_THRESHOLD, DEFAULT_DETECTION_THRESHOLD)
        
        # State
        self.is_filling = False
        self.is_draining = False
        self.last_volume = None
        self.last_update = None
        
        # Current event tracking
        self.event_start_time = None
        self.event_start_volume = None
        
        # Results to be exposed by sensors
        self.last_supply_stats = {}
        self.last_drain_stats = {}
        self.daily_supply_total = 0.0
        self.daily_consumption_total = 0.0
        self.typical_supply_times: list[time] = []

    def update_settings(self, config: dict[str, Any]) -> None:
        """Update thresholds from config."""
        self.threshold = config.get(CONF_DETECTION_THRESHOLD, DEFAULT_DETECTION_THRESHOLD)

    @callback
    def process_reading(self, volume: float, fill_rate: float) -> None:
        """Process a new volume/fill_rate reading to update state machine."""
        now = datetime.now(timezone.utc)
        
        if self.last_volume is None:
            self.last_volume = volume
            self.last_update = now
            return

        # ─── Supply Detection (Intelligent) ──────────────────────────────────
        if not self.is_filling and fill_rate >= self.threshold:
            # Start filling event
            self.is_filling = True
            self.event_start_time = now
            self.event_start_volume = volume
            _LOGGER.debug("Supply event started at %s (Vol: %s L)", now, volume)
        
        elif self.is_filling and fill_rate < (self.threshold / 2):
            # End filling event
            self.is_filling = False
            duration = (now - self.event_start_time).total_seconds() / 60.0
            amount = volume - self.event_start_volume
            
            if amount > 5.0:  # Only count if significant
                self.last_supply_stats = {
                    "start": self.event_start_time.isoformat(),
                    "end": now.isoformat(),
                    "amount": round(amount, 1),
                    "duration": round(duration, 1),
                    "final_pct": round((volume / self.entry.options.get(CONF_TANK_CAPACITY, 700)) * 100, 1)
                }
                self.daily_supply_total += amount
                self._record_supply_time(self.event_start_time.time())
                _LOGGER.info("Supply event ended: %s L in %s min", amount, duration)

        # ─── Drain Detection (Disaggregation) ────────────────────────────────
        if not self.is_filling:
            if not self.is_draining and fill_rate < -5.0: # Detect drop
                self.is_draining = True
                self.event_start_time = now
                self.event_start_volume = volume
            
            elif self.is_draining and fill_rate >= -2.0: # Back to stable
                self.is_draining = False
                amount = self.event_start_volume - volume
                duration = (now - self.event_start_time).total_seconds()
                
                if amount > 2.0: # Min detectable consumption
                    category = self._categorize_drain(amount, duration)
                    self.last_drain_stats = {
                        "amount": round(amount, 1),
                        "duration_sec": round(duration),
                        "category": category,
                        "time": now.isoformat()
                    }
                    self.daily_consumption_total += amount
                    _LOGGER.info("Consumption detected: %s (%s L)", category, amount)

        self.last_volume = volume
        self.last_update = now
        
        async_dispatcher_send(self.hass, f"{SIGNAL_ANALYTICS_UPDATE}_{self.entry.entry_id}")

    def _categorize_drain(self, amount: float, duration_sec: float) -> str:
        """Heuristic for consumption disaggregation."""
        if VOL_FLUSH_MIN <= amount <= VOL_FLUSH_MAX and duration_sec < 45:
            return DRAIN_CAT_FLUSH
        if VOL_SHOWER_MIN <= amount <= VOL_SHOWER_MAX and 180 < duration_sec < 900:
            return DRAIN_CAT_SHOWER
        if amount > VOL_LAUNDRY_MIN and duration_sec > 1200:
            return DRAIN_CAT_LAUNDRY
        return DRAIN_CAT_OTHER

    def _record_supply_time(self, start_time: time) -> None:
        """Track history of supply start times to discover windows."""
        self.typical_supply_times.append(start_time)
        if len(self.typical_supply_times) > 14: # Keep last 2 weeks approx
            self.typical_supply_times.pop(0)

    def reset_daily_stats(self) -> None:
        """Reset counters at midnight."""
        self.daily_supply_total = 0.0
        self.daily_consumption_total = 0.0
