"""Water Tank Monitor — Home Assistant custom integration.

Provides derived sensors (fill %, volume, fill rate) and binary alert sensors
from any numeric distance sensor (e.g. ESPHome ultrasonic).
"""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_VOLUME,
    CONF_DISTANCE_SENSOR,
    CONF_MAX_DISTANCE,
    CONF_MIN_DISTANCE,
    CONF_TANK_CAPACITY,
    DOMAIN,
    SERVICE_CALIBRATE_EMPTY,
    SERVICE_CALIBRATE_FULL,
    SERVICE_RESET_CALIBRATION_BOUNDS,
    SERVICE_SET_VOLUME,
    SIGNAL_RESET_BOUNDS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "binary_sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Water Tank Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {**entry.data, **entry.options}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Water Tank Monitor services."""

    async def _async_get_entry_from_device(device_id: str) -> ConfigEntry | None:
        """Get config entry ID from a device ID."""
        registry = dr.async_get(hass)
        device = registry.async_get(device_id)
        if not device:
            return None
        for entry_id in device.config_entries:
            if entry := hass.config_entries.async_get_entry(entry_id):
                if entry.domain == DOMAIN:
                    return entry
        return None

    async def handle_calibrate(call: ServiceCall) -> None:
        """Handle calibration service calls."""
        device_id = call.data.get("device_id")
        if not device_id:
            # If called without explicit device_id (e.g. from UI with target)
            # HA might pass it differently depending on the selector.
            # But the selector I used should provide devices.
            errors = call.data.get("device_id")
            _LOGGER.error("No device ID provided for calibration: %s", call.data)
            return

        entry = await _async_get_entry_from_device(device_id)
        if not entry:
            _LOGGER.error("No Water Tank Monitor config entry found for device %s", device_id)
            return

        # Get current sensor reading
        distance_sensor_id = entry.options.get(CONF_DISTANCE_SENSOR) or entry.data.get(CONF_DISTANCE_SENSOR)
        state = hass.states.get(distance_sensor_id)
        if not state or state.state in ("unknown", "unavailable"):
            _LOGGER.error("Distance sensor %s is not available for calibration", distance_sensor_id)
            return

        try:
            current_distance = float(state.state)
        except ValueError:
            _LOGGER.error("Distance sensor %s provided non-numeric value: %s", distance_sensor_id, state.state)
            return

        new_options = dict(entry.options)
        if call.service == SERVICE_CALIBRATE_FULL:
            new_options[CONF_MIN_DISTANCE] = current_distance
        else:
            new_options[CONF_MAX_DISTANCE] = current_distance

        hass.config_entries.async_update_entry(entry, options=new_options)
        _LOGGER.info(
            "Calibrated %s to %s for device %s",
            "full" if call.service == SERVICE_CALIBRATE_FULL else "empty",
            current_distance,
            device_id
        )

    async def handle_set_volume(call: ServiceCall) -> None:
        """Handle volume adjustment service call."""
        device_id = call.data.get("device_id")
        volume = call.data.get(ATTR_VOLUME)

        entry = await _async_get_entry_from_device(device_id)
        if not entry:
            return

        new_options = dict(entry.options)
        new_options[CONF_TANK_CAPACITY] = float(volume)
        hass.config_entries.async_update_entry(entry, options=new_options)
        _LOGGER.info("Updated tank volume to %s L for device %s", volume, device_id)

    async def handle_reset_bounds(call: ServiceCall) -> None:
        """Handle calibration bounds reset service call."""
        device_id = call.data.get("device_id")
        entry = await _async_get_entry_from_device(device_id)
        if not entry:
            return

        async_dispatcher_send(hass, f"{SIGNAL_RESET_BOUNDS}_{entry.entry_id}")
        _LOGGER.info("Reset calibration bounds for device %s", device_id)

    # Register services
    # Note: Service descriptions are in services.yaml
    hass.services.async_register(
        DOMAIN,
        SERVICE_CALIBRATE_FULL,
        handle_calibrate,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CALIBRATE_EMPTY,
        handle_calibrate,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_VOLUME,
        handle_set_volume,
        schema=vol.Schema({
            vol.Required("device_id"): str,
            vol.Required(ATTR_VOLUME): vol.Coerce(float),
        })
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_CALIBRATION_BOUNDS,
        handle_reset_bounds,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
