# Changelog

All notable changes to **Z2M Arrival Sensor** (Nexa Project by Manu Escaño).

## 0.2.0 — 2026-11-14

- Brand icon and logo (light and dark) in `custom_components/z2m_arrival_sensor/brand/`, shown in Home Assistant 2026.3+.
- Nexa Project by Manu Escaño signature in the source files, the setup and options dialogs and the README.
- `codeowners` set in the manifest.
- Full documentation: how it works, default patterns, Alarmo example, troubleshooting, removal.
- MIT license.
- Validated against a test plan on a real installation (Home Assistant OS, Zigbee2MQTT 2.14.3 with EmberZNet 7.4.3, two STSS-PRES-001, Alarmo).

## 0.1.0 — 2026-11-14

- First version.
- Follows the Zigbee2MQTT add-on log through the Supervisor and detects SmartThings arrival beacons (profile `0xFC01`, cluster `0xFC05`).
- One presence `binary_sensor` per configured sensor with `on` / `off` / `unavailable`; never `off` without a live log stream and Zigbee traffic.
- Network address mapping from `zigbee2mqtt/bridge/devices` and rejoin lines.
- Configurable patterns, timeouts, add-on slug and base topic in the UI (config and options flow, English and Spanish).
