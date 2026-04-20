"""Config flow for Water Tank Monitor."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CRITICAL_THRESHOLD,
    CONF_DISTANCE_SENSOR,
    CONF_LOW_THRESHOLD,
    CONF_MAX_DISTANCE,
    CONF_MIN_DISTANCE,
    CONF_TANK_CAPACITY,
    DEFAULT_CRITICAL_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_MAX_DISTANCE,
    DEFAULT_MIN_DISTANCE,
    DEFAULT_TANK_CAPACITY,
    DOMAIN,
)


def _build_schema(defaults: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DISTANCE_SENSOR,
                default=defaults.get(CONF_DISTANCE_SENSOR, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            ),
            vol.Optional(
                CONF_MIN_DISTANCE,
                default=defaults.get(CONF_MIN_DISTANCE, DEFAULT_MIN_DISTANCE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.0,
                    max=10.0,
                    step=0.01,
                    unit_of_measurement="m",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_MAX_DISTANCE,
                default=defaults.get(CONF_MAX_DISTANCE, DEFAULT_MAX_DISTANCE),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.0,
                    max=10.0,
                    step=0.01,
                    unit_of_measurement="m",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_TANK_CAPACITY,
                default=defaults.get(CONF_TANK_CAPACITY, DEFAULT_TANK_CAPACITY),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=1_000_000,
                    step=1,
                    unit_of_measurement="L",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_LOW_THRESHOLD,
                default=defaults.get(CONF_LOW_THRESHOLD, DEFAULT_LOW_THRESHOLD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=99,
                    step=1,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
            vol.Optional(
                CONF_CRITICAL_THRESHOLD,
                default=defaults.get(CONF_CRITICAL_THRESHOLD, DEFAULT_CRITICAL_THRESHOLD),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=99,
                    step=1,
                    unit_of_measurement="%",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            ),
        }
    )


def _validate(user_input: dict) -> str | None:
    """Return error key or None."""
    if float(user_input[CONF_MIN_DISTANCE]) >= float(user_input[CONF_MAX_DISTANCE]):
        return "invalid_distances"
    if float(user_input[CONF_CRITICAL_THRESHOLD]) >= float(user_input[CONF_LOW_THRESHOLD]):
        return "invalid_thresholds"
    return None


class WaterTankMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            error = _validate(user_input)
            if error:
                errors["base"] = error
            else:
                sensor_id = user_input[CONF_DISTANCE_SENSOR]
                await self.async_set_unique_id(f"{DOMAIN}_{sensor_id}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Water Tank Monitor ({sensor_id})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "WaterTankMonitorOptionsFlow":
        return WaterTankMonitorOptionsFlow()


class WaterTankMonitorOptionsFlow(config_entries.OptionsFlow):
    """Allow reconfiguring parameters without reinstalling."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            error = _validate(user_input)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(current),
            errors=errors,
        )
