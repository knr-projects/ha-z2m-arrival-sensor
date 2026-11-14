"""Follows the Zigbee2MQTT add-on log and tracks arrival-sensor beacons."""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import time
from typing import Any

import aiohttp

from homeassistant.components import mqtt
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ADDON_SLUG,
    CONF_BASE_TOPIC,
    CONF_BEACON_REGEX,
    CONF_HEARTBEAT_REGEX,
    CONF_HEARTBEAT_TIMEOUT,
    CONF_MAX_LINE_AGE,
    CONF_REJOIN_REGEX,
    CONF_TIMEOUT,
    DOMAIN,
    SIGNAL_UPDATE,
)

_LOGGER = logging.getLogger(__name__)

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_TIMESTAMP = re.compile(r"^\[(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")


def _to_int(value: str) -> int | None:
    try:
        return int(value, 0)
    except ValueError:
        try:
            return int(value)
        except ValueError:
            return None


class LogWatcher:
    """Reads the add-on log stream and keeps the last beacon per device."""

    def __init__(self, hass: HomeAssistant, entry_id: str, cfg: dict[str, Any]) -> None:
        self.hass = hass
        self.signal = SIGNAL_UPDATE.format(entry_id)
        self.slug: str = cfg[CONF_ADDON_SLUG]
        self.base_topic: str = cfg[CONF_BASE_TOPIC].rstrip("/")
        self.timeout = float(cfg[CONF_TIMEOUT])
        self.heartbeat_timeout = float(cfg[CONF_HEARTBEAT_TIMEOUT])
        self.max_line_age = float(cfg[CONF_MAX_LINE_AGE])
        self.beacon_re = re.compile(cfg[CONF_BEACON_REGEX])
        self.heartbeat_re = re.compile(cfg[CONF_HEARTBEAT_REGEX])
        rejoin = cfg.get(CONF_REJOIN_REGEX) or ""
        self.rejoin_re = re.compile(rejoin) if rejoin else None

        self.connected = False
        self.connected_since: float | None = None
        self.last_heartbeat: float | None = None
        self.beacon_by_nwk: dict[int, float] = {}
        self.beacon_by_ieee: dict[str, float] = {}
        self.ieee_to_nwk: dict[str, int] = {}

        self._task: asyncio.Task | None = None
        self._unsub_mqtt = None

    async def async_start(self) -> None:
        self._unsub_mqtt = await mqtt.async_subscribe(
            self.hass, f"{self.base_topic}/bridge/devices", self._on_devices
        )
        self._task = self.hass.async_create_background_task(
            self._run(), f"{DOMAIN}_follow_{self.slug}"
        )

    async def async_stop(self) -> None:
        if self._unsub_mqtt:
            self._unsub_mqtt()
            self._unsub_mqtt = None
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    # ---- MQTT: ieee -> network address mapping -------------------------

    @callback
    def _on_devices(self, msg: Any) -> None:
        try:
            devices = json.loads(msg.payload)
        except (ValueError, TypeError):
            return
        mapping: dict[str, int] = {}
        for dev in devices if isinstance(devices, list) else []:
            ieee = str(dev.get("ieee_address", "")).lower()
            nwk = dev.get("network_address")
            if ieee and isinstance(nwk, int):
                mapping[ieee] = nwk
        if mapping:
            self.ieee_to_nwk.update(mapping)
            async_dispatcher_send(self.hass, self.signal)

    # ---- Log stream ----------------------------------------------------

    async def _run(self) -> None:
        token = os.environ.get("SUPERVISOR_TOKEN", "")
        host = os.environ.get("SUPERVISOR", "supervisor")
        url = f"http://{host}/addons/{self.slug}/logs/follow"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "text/plain",
            # start at the end of the journal: no replay of old lines
            "Range": "entries=:-1:",
        }
        session = async_get_clientsession(self.hass)
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=None)
        backoff = 5
        while True:
            try:
                async with session.get(url, headers=headers, timeout=timeout) as resp:
                    resp.raise_for_status()
                    self._set_connected(True)
                    backoff = 5
                    async for raw in resp.content:
                        self._handle_line(raw.decode("utf-8", "replace"))
                _LOGGER.debug("Log stream for %s ended", self.slug)
            except asyncio.CancelledError:
                self._set_connected(False)
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Log stream for add-on %s interrupted: %s", self.slug, err)
            self._set_connected(False)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60)

    def _set_connected(self, value: bool) -> None:
        if value == self.connected:
            return
        self.connected = value
        self.connected_since = time.monotonic() if value else None
        async_dispatcher_send(self.hass, self.signal)

    def _is_fresh(self, line: str) -> bool:
        if self.max_line_age <= 0:
            return True
        match = _TIMESTAMP.match(line)
        if not match:
            return True
        parsed = dt_util.parse_datetime(f"{match.group(1)}T{match.group(2)}")
        if parsed is None:
            return True
        if parsed.tzinfo is None:
            tz = getattr(dt_util, "get_default_time_zone", lambda: dt_util.DEFAULT_TIME_ZONE)()
            parsed = parsed.replace(tzinfo=tz)
        return abs((dt_util.now() - parsed).total_seconds()) <= self.max_line_age

    def _handle_line(self, line: str) -> None:
        line = _ANSI.sub("", line).strip()
        if not line:
            return

        if self.rejoin_re and (match := self.rejoin_re.search(line)):
            groups = match.groupdict()
            nwk = _to_int(groups.get("nwk") or "")
            ieee = (groups.get("ieee") or "").lower()
            if ieee and nwk is not None:
                self.ieee_to_nwk[ieee] = nwk

        if not self._is_fresh(line):
            return

        now = time.monotonic()
        if self.heartbeat_re.search(line):
            self.last_heartbeat = now

        match = self.beacon_re.search(line)
        if not match:
            return
        groups = match.groupdict()
        if groups.get("ieee"):
            self.beacon_by_ieee[groups["ieee"].lower()] = now
        elif groups.get("nwk"):
            nwk = _to_int(groups["nwk"])
            if nwk is None:
                return
            self.beacon_by_nwk[nwk] = now
        else:
            return
        self.last_heartbeat = now
        async_dispatcher_send(self.hass, self.signal)

    # ---- State for entities -------------------------------------------

    def state_for(self, ieee: str) -> tuple[bool, bool | None, dict[str, Any]]:
        """Return (available, is_on, attributes) for a configured device."""
        now = time.monotonic()
        nwk = self.ieee_to_nwk.get(ieee)
        attrs: dict[str, Any] = {"ieee_address": ieee, "network_address": nwk}

        # No log stream or no Zigbee traffic at all: we do not know.
        if not self.connected or self.connected_since is None:
            return False, None, attrs
        if self.last_heartbeat is None or now - self.last_heartbeat > self.heartbeat_timeout:
            return False, None, attrs

        last = self.beacon_by_ieee.get(ieee)
        if last is None and nwk is not None:
            last = self.beacon_by_nwk.get(nwk)
        if last is not None and now - last <= self.timeout:
            return True, True, attrs

        # Right after (re)connecting we have not waited long enough to say "away".
        if now - self.connected_since < self.timeout:
            return False, None, attrs
        # Unknown network address and no IEEE-based beacon: cannot decide.
        if nwk is None and ieee not in self.beacon_by_ieee:
            return False, None, attrs
        return True, False, attrs
