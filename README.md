# Z2M Arrival Sensor

Workaround for SmartThings arrival sensors (STSS-PRES-001 / PGC410) on Zigbee2MQTT with an **ember** coordinator, where the arrival beacons (profile `0xFC01`, cluster `0xFC05`) reach the adapter but are never processed, so `presence` stays N/A. See [Koenkk/zigbee2mqtt#33697](https://github.com/Koenkk/zigbee2mqtt/issues/33697).

The integration follows the Zigbee2MQTT add-on log through the Supervisor, detects the beacons and creates one `binary_sensor` (device class `presence`) per sensor. Zigbee2MQTT itself is not modified.

## States

| State | Meaning |
|---|---|
| `on` | A beacon was seen within the timeout (default 100 s) |
| `off` | No beacon within the timeout **while the log stream and the Zigbee network are alive** |
| `unavailable` | No log stream, no Zigbee traffic at all, unknown network address, or still warming up after start |

`unavailable` never means "away". In automations (e.g. Alarmo), only treat `off` as away.

## Requirements

- Home Assistant OS or Supervised (the log is read through the Supervisor).
- Zigbee2MQTT add-on with an ember adapter and the MQTT integration.
- Debug logging for the `zh:ember:ezsp` namespace only. Publish to `zigbee2mqtt/bridge/request/options`:

```json
{"options":{"advanced":{"log_namespaced_levels":{"zh:ember:ezsp":"debug"}}}}
```

The global `log_level` can stay at `info`.

## Installation (HACS)

1. HACS → ⋮ → Custom repositories → add this repository URL, type **Integration**.
2. Install **Z2M Arrival Sensor** and restart Home Assistant.
3. Settings → Devices & services → Add integration → **Z2M Arrival Sensor**.

## Configuration

- **Sensors**: one per line, `IEEE = name`, e.g. `0x0123456789abcdef = Keys`.
- **Timeout**: seconds without beacon before `off` (default 100; the sensors beacon every 20 s).
- **Heartbeat timeout**: seconds without any Zigbee frame in the log before `unavailable` (default 120).
- **Patterns** (regular expressions), editable in the options if a Zigbee2MQTT update changes the log format:
  - Beacon: must contain a named group `nwk` (network address) or `ieee`.
  - Heartbeat: any line proving Zigbee traffic.
  - Rejoin (optional): groups `nwk` and `ieee`, keeps the address mapping fresh after a rejoin.
- **Max line age**: ignore log lines older than this (default 60 s, 0 disables).

The network address of each sensor is learned from `zigbee2mqtt/bridge/devices` and from rejoin lines, so it keeps working if the address changes.

When Zigbee2MQTT fixes the issue, remove this integration and use the native Zigbee2MQTT entities again.
