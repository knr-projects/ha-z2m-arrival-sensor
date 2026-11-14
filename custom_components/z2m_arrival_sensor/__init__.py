# Z2M Arrival Sensor — Nexa Project by Manu Escaño
# https://github.com/manuelem1984/ha-z2m-arrival-sensor
"""Z2M Arrival Sensor: presence for SmartThings arrival sensors from the Zigbee2MQTT log."""
from __future__ import annotations

import logging
import os

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULTS
from .watcher import LogWatcher

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not os.environ.get("SUPERVISOR_TOKEN"):
        _LOGGER.error("Supervisor not available: this integration needs Home Assistant OS or Supervised")
        return False
    if not await mqtt.async_wait_for_mqtt_client(hass):
        raise ConfigEntryNotReady("MQTT is not available")

    cfg = {**DEFAULTS, **entry.data, **entry.options}
    watcher = LogWatcher(hass, entry.entry_id, cfg)
    await watcher.async_start()
    entry.runtime_data = watcher

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
