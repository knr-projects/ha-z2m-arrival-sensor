# Z2M Arrival Sensor — Nexa Project by Manu Escaño
# https://github.com/knr-projects/ha-z2m-arrival-sensor
"""Presence binary sensors fed by the Zigbee2MQTT log."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_SENSORS, DEFAULTS, DOMAIN, parse_sensors
from .watcher import LogWatcher

REFRESH_INTERVAL = timedelta(seconds=5)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    watcher: LogWatcher = entry.runtime_data
    cfg = {**DEFAULTS, **entry.data, **entry.options}
    async_add_entities(
        ArrivalPresenceSensor(watcher, entry.entry_id, ieee, name)
        for ieee, name in parse_sensors(cfg[CONF_SENSORS])
    )


class ArrivalPresenceSensor(BinarySensorEntity):
    """Presence of one arrival sensor."""

    _attr_device_class = BinarySensorDeviceClass.PRESENCE
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, watcher: LogWatcher, entry_id: str, ieee: str, name: str) -> None:
        self._watcher = watcher
        self._ieee = ieee
        self._last: tuple[Any, ...] | None = None
        self._attr_unique_id = f"{entry_id}_{ieee}"
        self._attr_available = False
        self._attr_is_on = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ieee)},
            name=name,
            manufacturer="SmartThings",
            model="Arrival sensor (Z2M log)",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._watcher.signal, self._refresh)
        )
        self.async_on_remove(
            async_track_time_interval(self.hass, self._tick, REFRESH_INTERVAL)
        )
        self._refresh()

    @callback
    def _tick(self, _now: Any) -> None:
        self._refresh()

    @callback
    def _refresh(self) -> None:
        available, is_on, attrs = self._watcher.state_for(self._ieee)
        snapshot = (available, is_on, tuple(sorted(attrs.items())))
        if snapshot == self._last:
            return
        self._last = snapshot
        self._attr_available = available
        self._attr_is_on = is_on
        self._attr_extra_state_attributes = attrs
        self.async_write_ha_state()
