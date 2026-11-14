<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="custom_components/z2m_arrival_sensor/brand/dark_logo@2x.png">
    <img alt="Z2M Arrival Sensor — Nexa Project by Manu Escaño" src="custom_components/z2m_arrival_sensor/brand/logo@2x.png" width="480">
  </picture>
</p>

# Z2M Arrival Sensor

Presence for **SmartThings arrival sensors** (STSS-PRES-001 / PGC410) on **Zigbee2MQTT with an ember coordinator**, read directly from the Zigbee2MQTT log.

## Why this exists

With an ember-based coordinator (EmberZNet, e.g. Aeotec Z-Stick 10 Pro), the arrival beacons these sensors send every 20 s use the SmartThings private profile (`0xFC01`, cluster `0xFC05`). They reach the adapter, but Zigbee2MQTT drops them before they get to the device converter, so `presence` and `battery` stay N/A forever. The sensors are paired, in range and transmitting; Zigbee2MQTT just never processes the frames.

Reported upstream: [Koenkk/zigbee2mqtt#33697](https://github.com/Koenkk/zigbee2mqtt/issues/33697).

This integration is a workaround that does not modify Zigbee2MQTT, so it survives Zigbee2MQTT updates.

## How it works

1. Zigbee2MQTT logs every incoming frame of the `zh:ember:ezsp` namespace at debug level, including the arrival beacons.
2. The integration follows the Zigbee2MQTT add-on log live through the Supervisor API (`/addons/<slug>/logs/follow`), starting at the end of the log (no replay of old lines).
3. Each line is matched against three configurable regular expressions:
   - **Beacon**: an arrival beacon from a sensor (identified by its network address or IEEE).
   - **Heartbeat**: any incoming Zigbee frame, proving the log stream and the Zigbee network are alive.
   - **Rejoin**: a rejoin line that links a network address to an IEEE address.
4. The current network address of every device is also taken from the retained MQTT topic `zigbee2mqtt/bridge/devices`, so a sensor keeps working when its short address changes after a rejoin.
5. One `binary_sensor` (device class `presence`) is created per configured sensor and refreshed every 5 s and on every beacon.

## States

| State | Meaning |
|---|---|
| `on` | A beacon was seen within the timeout (default 100 s) |
| `off` | No beacon within the timeout **while the log stream and the Zigbee network are alive** |
| `unavailable` | No log stream, no Zigbee traffic at all for the heartbeat timeout, unknown network address, or still warming up after start or reconnect |

`unavailable` never means "away". This is the main difference with the native Zigbee2MQTT entity, which reports `off` when it simply stops hearing the sensor. In automations, only treat `off` as away.

Each entity exposes the attributes `ieee_address` and `network_address`.

> **Heartbeat note:** the `off` state needs some Zigbee traffic in the log. If the arrival sensors are the only active devices and both are away, the entities go `unavailable` after the heartbeat timeout instead of `off`. Any mains-powered device reporting periodically (e.g. a smart plug) keeps the heartbeat alive.

## Requirements

- Home Assistant OS or Supervised (the log is read through the Supervisor). Container and Core installs are not supported.
- Zigbee2MQTT **add-on** with an **ember** adapter.
- The MQTT integration connected to the same broker as Zigbee2MQTT.
- Home Assistant 2026.3 or newer to show the integration icon and logo (the integration itself works on 2024.11+).
- Debug logging for the `zh:ember:ezsp` namespace only (see below).

## Installation (HACS)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/knr-projects/ha-z2m-arrival-sensor`, type **Integration**.
2. Install **Z2M Arrival Sensor** and restart Home Assistant.
3. Enable the namespace debug log in Zigbee2MQTT (next section).
4. Settings → Devices & services → **Add integration** → **Z2M Arrival Sensor**.

### Enable the namespace debug log in Zigbee2MQTT

Publish this payload to `zigbee2mqtt/bridge/request/options` (Settings → Devices & services → MQTT → Configure → Publish a packet):

```json
{"options":{"advanced":{"log_namespaced_levels":{"zh:ember:ezsp":"debug"}}}}
```

The global `log_level` can stay at `info`; only that namespace becomes verbose. Zigbee2MQTT answers on `zigbee2mqtt/bridge/response/options` and no restart is needed.

## Configuration

All settings are made in the UI and can be changed later with **Configure** on the integration.

| Option | Default | Description |
|---|---|---|
| Sensors | — | One per line: `IEEE = name`, e.g. `0x0123456789abcdef = Keys` |
| Timeout | `100` s | Seconds without beacon before `off`. The sensors beacon every 20 s |
| Heartbeat timeout | `120` s | Seconds without any Zigbee frame in the log before `unavailable` |
| Add-on slug | `45df7312_zigbee2mqtt` | Slug of the Zigbee2MQTT add-on (shown in the add-on URL) |
| Base topic | `zigbee2mqtt` | Zigbee2MQTT MQTT base topic |
| Beacon pattern | see below | Must contain a named group `nwk` or `ieee` |
| Heartbeat pattern | see below | Any line proving Zigbee traffic |
| Rejoin pattern | see below | Optional; named groups `nwk` and `ieee` |
| Max line age | `60` s | Ignore log lines older than this (`0` disables the check) |

Default patterns (Zigbee2MQTT 2.14 with the ember driver):

```text
Beacon:    ezspIncomingMessageHandler:.*"profileId":64513,"clusterId":64517.*"senderShortId":(?P<nwk>\d+)
Heartbeat: ezspIncomingMessageHandler:
Rejoin:    newNodeId=(?P<nwk>\d+) newNodeEui64=(?P<ieee>0x[0-9a-fA-F]{16})
```

If a Zigbee2MQTT update changes the log format, adapt the patterns in the options. Nothing else needs to change. If the patterns stop matching, the entities fall back to `unavailable`, never to `off`.

## Example: Alarmo

Disarm when any sensor arrives, arm away only when **both** are explicitly `off` for one minute. `unavailable` or `unknown` never arms.

```yaml
alias: Alarm - automatic control by arrival sensors
triggers:
  - trigger: state
    entity_id:
      - binary_sensor.keys_1
      - binary_sensor.keys_2
    to: "on"
    id: arrive
  - trigger: state
    entity_id:
      - binary_sensor.keys_1
      - binary_sensor.keys_2
    to: "off"
    for: "00:01:00"
    id: leave
actions:
  - choose:
      - conditions:
          - condition: trigger
            id: arrive
          - condition: state
            entity_id: alarm_control_panel.alarmo
            state: [armed_away, arming, pending]
        sequence:
          - action: alarm_control_panel.alarm_disarm
            target:
              entity_id: alarm_control_panel.alarmo
      - conditions:
          - condition: trigger
            id: leave
          - condition: state
            entity_id: binary_sensor.keys_1
            state: "off"
          - condition: state
            entity_id: binary_sensor.keys_2
            state: "off"
          - condition: state
            entity_id: alarm_control_panel.alarmo
            state: disarmed
        sequence:
          - action: alarm_control_panel.alarm_arm_away
            target:
              entity_id: alarm_control_panel.alarmo
mode: queued
```

## Troubleshooting

| Symptom | Check |
|---|---|
| Entities always `unavailable` | Is the namespace debug log enabled? Open the Zigbee2MQTT add-on log and look for `ezspIncomingMessageHandler` lines. Is the add-on slug correct? |
| A sensor is `unavailable` but others work | The IEEE in the configuration must match Zigbee2MQTT. `network_address` stays empty until the address is known from `bridge/devices` or a rejoin |
| Sensor stays `off` while at home | Look in the add-on log for lines with `"profileId":64513` and its network address. Removing and reinserting the battery forces a rejoin |
| Nothing works after a Zigbee2MQTT update | Compare the log lines with the patterns and adjust them in the options |
| Icon not shown | Requires Home Assistant 2026.3+. Hard-refresh the browser (Ctrl+F5) after updating |

Integration logs: add to `configuration.yaml`

```yaml
logger:
  logs:
    custom_components.z2m_arrival_sensor: debug
```

## Updating and removal

- Updates are delivered through HACS. Restart Home Assistant after updating.
- **When Zigbee2MQTT fixes the issue:** remove the integration (Settings → Devices & services), uninstall it in HACS, switch your automations back to the native Zigbee2MQTT entities, and remove `zh:ember:ezsp` from `log_namespaced_levels`.

## Limitations

- Only the SmartThings arrival beacon on ember adapters is covered by the default patterns. Other adapters log differently.
- `battery` is not provided.
- The namespace debug log makes the Zigbee2MQTT log bigger.
- Home Assistant OS or Supervised only.

## Tested with

Validated against a test plan on a real installation:

- Home Assistant OS, Home Assistant Core 2026.11
- Zigbee2MQTT add-on 2.14.3 (ember driver)
- Aeotec Z-Stick 10 Pro, EmberZNet 7.4.3
- 2 × SmartThings STSS-PRES-001 (PGC410)
- Alarmo

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE) © 2026 Manu Escaño (Nexa Project)

---

**Z2M Arrival Sensor** is part of **Nexa Project by Manu Escaño**.
