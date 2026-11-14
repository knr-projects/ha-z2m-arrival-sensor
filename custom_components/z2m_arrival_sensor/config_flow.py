# Z2M Arrival Sensor — Nexa Project by Manu Escaño
# https://github.com/knr-projects/ha-z2m-arrival-sensor
"""Config and options flow for Z2M Arrival Sensor."""
from __future__ import annotations

import os
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_ADDON_SLUG,
    CONF_BASE_TOPIC,
    CONF_BEACON_REGEX,
    CONF_HEARTBEAT_REGEX,
    CONF_HEARTBEAT_TIMEOUT,
    CONF_MAX_LINE_AGE,
    CONF_REJOIN_REGEX,
    CONF_SENSORS,
    CONF_TIMEOUT,
    DEFAULTS,
    DOMAIN,
    parse_sensors,
)

_INT_KEYS = (CONF_TIMEOUT, CONF_HEARTBEAT_TIMEOUT, CONF_MAX_LINE_AGE)


def _seconds(minimum: int, maximum: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(
            min=minimum, max=maximum, step=1, unit_of_measurement="s",
            mode=NumberSelectorMode.BOX,
        )
    )


def _schema(values: dict[str, Any]) -> vol.Schema:
    v = {**DEFAULTS, **values}
    return vol.Schema(
        {
            vol.Required(CONF_SENSORS, default=v[CONF_SENSORS]): TextSelector(
                TextSelectorConfig(multiline=True)
            ),
            vol.Required(CONF_TIMEOUT, default=v[CONF_TIMEOUT]): _seconds(20, 3600),
            vol.Required(CONF_HEARTBEAT_TIMEOUT, default=v[CONF_HEARTBEAT_TIMEOUT]): _seconds(20, 3600),
            vol.Required(CONF_ADDON_SLUG, default=v[CONF_ADDON_SLUG]): str,
            vol.Required(CONF_BASE_TOPIC, default=v[CONF_BASE_TOPIC]): str,
            vol.Required(CONF_BEACON_REGEX, default=v[CONF_BEACON_REGEX]): str,
            vol.Required(CONF_HEARTBEAT_REGEX, default=v[CONF_HEARTBEAT_REGEX]): str,
            vol.Optional(CONF_REJOIN_REGEX, default=v[CONF_REJOIN_REGEX]): str,
            vol.Required(CONF_MAX_LINE_AGE, default=v[CONF_MAX_LINE_AGE]): _seconds(0, 3600),
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    data = dict(user_input)
    for key in _INT_KEYS:
        data[key] = int(data[key])
    data.setdefault(CONF_REJOIN_REGEX, "")
    return data


def _validate(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for key in (CONF_BEACON_REGEX, CONF_HEARTBEAT_REGEX, CONF_REJOIN_REGEX):
        if not data.get(key):
            continue
        try:
            re.compile(data[key])
        except re.error:
            errors[key] = "invalid_regex"
    if CONF_BEACON_REGEX not in errors:
        groups = set(re.compile(data[CONF_BEACON_REGEX]).groupindex)
        if not groups & {"nwk", "ieee"}:
            errors[CONF_BEACON_REGEX] = "missing_group"
    try:
        if not parse_sensors(data[CONF_SENSORS]):
            errors[CONF_SENSORS] = "no_sensors"
    except ValueError:
        errors[CONF_SENSORS] = "invalid_sensors"
    return errors


class Z2MArrivalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if not os.environ.get("SUPERVISOR_TOKEN"):
            return self.async_abort(reason="not_supervisor")
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            errors = _validate(data)
            if not errors:
                return self.async_create_entry(title="Z2M Arrival Sensor", data={}, options=data)
            user_input = data
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return Z2MArrivalOptionsFlow()


class Z2MArrivalOptionsFlow(config_entries.OptionsFlow):
    """Edit settings after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _clean(user_input)
            errors = _validate(data)
            if not errors:
                return self.async_create_entry(data=data)
            values = data
        else:
            values = dict(self.config_entry.options)
        return self.async_show_form(step_id="init", data_schema=_schema(values), errors=errors)
