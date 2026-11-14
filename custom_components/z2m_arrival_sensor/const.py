# Z2M Arrival Sensor — Nexa Project by Manu Escaño
# https://github.com/manuelem1984/ha-z2m-arrival-sensor
"""Constants for Z2M Arrival Sensor."""
from __future__ import annotations

import re

DOMAIN = "z2m_arrival_sensor"

CONF_SENSORS = "sensors"
CONF_TIMEOUT = "timeout"
CONF_HEARTBEAT_TIMEOUT = "heartbeat_timeout"
CONF_ADDON_SLUG = "addon_slug"
CONF_BASE_TOPIC = "base_topic"
CONF_BEACON_REGEX = "beacon_regex"
CONF_HEARTBEAT_REGEX = "heartbeat_regex"
CONF_REJOIN_REGEX = "rejoin_regex"
CONF_MAX_LINE_AGE = "max_line_age"

DEFAULTS: dict = {
    CONF_SENSORS: "",
    CONF_TIMEOUT: 100,
    CONF_HEARTBEAT_TIMEOUT: 120,
    CONF_ADDON_SLUG: "45df7312_zigbee2mqtt",
    CONF_BASE_TOPIC: "zigbee2mqtt",
    # SmartThings arrival beacon: profile 0xFC01 (64513), cluster 0xFC05 (64517)
    CONF_BEACON_REGEX: (
        r'ezspIncomingMessageHandler:.*"profileId":64513,"clusterId":64517'
        r'.*"senderShortId":(?P<nwk>\d+)'
    ),
    # Any incoming frame proves the log stream and the Zigbee network are alive
    CONF_HEARTBEAT_REGEX: r"ezspIncomingMessageHandler:",
    CONF_REJOIN_REGEX: r"newNodeId=(?P<nwk>\d+) newNodeEui64=(?P<ieee>0x[0-9a-fA-F]{16})",
    CONF_MAX_LINE_AGE: 60,
}

SIGNAL_UPDATE = DOMAIN + "_update_{}"

_SENSOR_LINE = re.compile(r"^\s*(0x[0-9a-fA-F]{16})\s*[=:;,]\s*(.+?)\s*$")


def parse_sensors(text: str) -> list[tuple[str, str]]:
    """Parse lines like '0x0123456789abcdef = Keys'."""
    result: list[tuple[str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _SENSOR_LINE.match(line)
        if not match:
            raise ValueError(line)
        result.append((match.group(1).lower(), match.group(2)))
    return result
