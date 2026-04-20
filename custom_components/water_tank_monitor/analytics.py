"""Intelligent analytics for Water Tank Monitor.

Tracks supply events and monitors for leaks with temporal stabilization.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, time, timezone
from statistics import median
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_DETECTION_THRESHOLD,
    CONF_LEAK_DURATION_THRESHOLD,
    CONF_LEAK_RATE_THRESHOLD,
    CONF_TANK_CAPACITY,
    DEFAULT_DETECTION_THRESHOLD,
    DEFAULT_LEAK_DURATION_THRESHOLD,
    DEFAULT_LEAK_RATE_THRESHOLD,
    DOMAIN,
    SIGNAL_ANALYTICS_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

# Constants for detection
SUPPLY_CONFIRMATION_SEC = 60
SUPPLY_END_TIMEOUT_SEC = 30
LEAK_MIN_RATE = 0.5  # Ignore drops below 0.5 L/h for leak detection
USAGE_THRESHOLD_RATE = 15.0 # drops faster than this are considered usage, not leaks
HISTORY_MAX_LEN = 120 # approx 2-4 minutes depending on update frequency


class WaterTankAnalytics:
    """Manages state machine and event detection for a water tank."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.threshold = entry.options.get(CONF_DETECTION_THRESHOLD, DEFAULT_DETECTION_THRESHOLD)
        self.leak_rate_threshold = entry.options.get(CONF_LEAK_RATE_THRESHOLD, DEFAULT_LEAK_RATE_THRESHOLD)
        self.leak_duration_min = entry.options.get(CONF_LEAK_DURATION_THRESHOLD, DEFAULT_LEAK_DURATION_THRESHOLD)
        
        # State
        self.is_filling = False
        self.is_leaking = False
        
        self.last_volume = None
        self.last_update = None
        self.smoothed_volume = None
        
        # Buffers
        self.history: deque[tuple[datetime, float]] = deque(maxlen=HISTORY_MAX_LEN)
        
        # Event tracking
        self.supply_start_time = None
        self.supply_start_volume = None
        self.leak_start_time = None
        
        # Results
        self.last_supply_stats = {}
        self.daily_supply_total = 0.0
        self.typical_supply_times: list[time] = []

    def update_settings(self, config: dict[str, Any]) -> None:
        """Update thresholds from config."""
        self.threshold = config.get(CONF_DETECTION_THRESHOLD, DEFAULT_DETECTION_THRESHOLD)
        self.leak_rate_threshold = config.get(CONF_LEAK_RATE_THRESHOLD, DEFAULT_LEAK_RATE_THRESHOLD)
        self.leak_duration_min = config.get(CONF_LEAK_DURATION_THRESHOLD, DEFAULT_LEAK_DURATION_THRESHOLD)

    @callback
    def process_reading(self, volume: float, fill_rate: float) -> None:
        """Process a new volume reading."""
        now = datetime.now(timezone.utc)
        self.history.append((now, volume))
        
        if self.last_volume is None:
            self.last_volume = volume
            self.smoothed_volume = volume
            self.last_update = now
            return

        # ─── Turbulence Filtering ───────────────────────────────────────────
        # Use median of last 15 readings during supply, or last 3 otherwise
        win_size = 15 if self.is_filling else 3
        if len(self.history) >= win_size:
            recent_vols = [r[1] for r in list(self.history)[-win_size:]]
            self.smoothed_volume = round(median(recent_vols), 2)
        else:
            self.smoothed_volume = volume

        # ─── Temporal Supply Detection ──────────────────────────────────────
        self._check_supply(now)
        
        # ─── Leak Detection ─────────────────────────────────────────────────
        self._check_leak(now, fill_rate)

        self.last_volume = volume
        self.last_update = now
        async_dispatcher_send(self.hass, f"{SIGNAL_ANALYTICS_UPDATE}_{self.entry.entry_id}")

    def _check_supply(self, now: datetime) -> None:
        """Verify supply with temporal confirmation."""
        if not self.is_filling:
            # Check for constant increase over 60s
            readings_1m = [r for r in self.history if (now - r[0]).total_seconds() <= SUPPLY_CONFIRMATION_SEC]
            if len(readings_1m) > 5:
                v_start = readings_1m[0][1]
                v_end = readings_1m[-1][1]
                increase = v_end - v_start
                # Must increase by at least 2L and have positive trend
                if increase >= 2.0:
                    # Check if mostly monotonic
                    is_monotonic = True
                    for i in range(1, len(readings_1m)):
                        if readings_1m[i][1] < readings_1m[i-1][1] - 0.5: # allow 0.5L jitter
                            is_monotonic = False
                            break
                    
                    if is_monotonic:
                        self.is_filling = True
                        self.supply_start_time = readings_1m[0][0]
                        self.supply_start_volume = v_start
                        _LOGGER.info("Water supply detected and confirmed (trend > 60s)")
        else:
            # Check if supply ended (no significant increase in last 30s)
            readings_30s = [r for r in self.history if (now - r[0]).total_seconds() <= SUPPLY_END_TIMEOUT_SEC]
            if len(readings_30s) > 3:
                max_v = max(r[1] for r in readings_30s)
                min_v = min(r[1] for r in readings_30s)
                # If variance is small and no upward trend
                if (max_v - min_v) < 1.0 or readings_30s[-1][1] <= readings_30s[0][1] + 0.2:
                    self._end_supply(now, readings_30s[-1][1])

    def _end_supply(self, now: datetime, end_volume: float) -> None:
        """Wrap up a supply event."""
        self.is_filling = False
        duration = (now - self.supply_start_time).total_seconds() / 60.0
        amount = end_volume - self.supply_start_volume
        
        if amount > 5.0:
            self.last_supply_stats = {
                "start": self.supply_start_time.isoformat(),
                "end": now.isoformat(),
                "amount": round(amount, 1),
                "duration_min": round(duration, 1),
            }
            self.daily_supply_total += amount
            self._record_supply_time(self.supply_start_time.time())
            _LOGGER.info("Supply event ended: %s L", round(amount, 1))

    def _check_leak(self, now: datetime, fill_rate: float) -> None:
        """Detect sustained small drops, ignoring high-flow usage interruptions."""
        
        # 1. Leak Zone: Constant small drop
        is_in_leak_zone = -USAGE_THRESHOLD_RATE < fill_rate < -self.leak_rate_threshold
        
        # 2. Usage Zone: High-flow consumption
        is_usage = fill_rate <= -USAGE_THRESHOLD_RATE
        
        # 3. Stable/Filling Zone: No significant drop or active supply
        is_stable_or_filling = fill_rate >= -self.leak_rate_threshold or self.is_filling

        if is_in_leak_zone:
            # Start or continue the timer
            if self.leak_start_time is None:
                self.leak_start_time = now
            
            elapsed = (now - self.leak_start_time).total_seconds() / 60.0
            if elapsed >= self.leak_duration_min:
                if not self.is_leaking:
                    self.is_leaking = True
                    _LOGGER.warning("Potential leak detected! Sustained drop of %s L/h", round(abs(fill_rate), 1))
        
        elif is_usage:
            # Suspension logic: 
            # If we were already timing a leak, we keep the leak_start_time as is.
            # We don't advance the detection but we don't punish the timer for a flush.
            # We effectively "pause" by just doing nothing.
            pass
            
        elif is_stable_or_filling:
            # Genuine reset condition: tank stopped dropping or is being filled
            self.leak_start_time = None
            self.is_leaking = False

    def _record_supply_time(self, start_time: time) -> None:
        """Track history of supply start times."""
        self.typical_supply_times.append(start_time)
        if len(self.typical_supply_times) > 14:
            self.typical_supply_times.pop(0)

    def reset_daily_stats(self) -> None:
        """Reset counters at midnight."""
        self.daily_supply_total = 0.0
