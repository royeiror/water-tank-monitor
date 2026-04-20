# Water Tank Monitor

A [Home Assistant](https://www.home-assistant.io/) custom integration that turns any numeric distance sensor into a full water-tank monitoring system — fill percentage, volume, fill rate, and configurable alerts.

Built for use with an **ESP8266/ESP32 + HC-SR04 ultrasonic sensor** flashed with ESPHome, but works with any HA distance sensor entity.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

---

## Features

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.water_tank_monitor_fill_percentage` | Sensor | Fill level 0–100 % |
| `sensor.water_tank_monitor_water_volume` | Sensor | Volume in liters |
| `sensor.water_tank_monitor_fill_rate` | Sensor | Fill/drain rate in L/h |
| `binary_sensor.water_tank_monitor_low_level` | Binary sensor | ON when below low threshold |
| `binary_sensor.water_tank_monitor_critical_level` | Binary sensor | ON when below critical threshold |
| `binary_sensor.water_tank_monitor_tank_full` | Binary sensor | ON when tank ≥ 95 % full |

- **Event-driven** — no polling; updates instantly when the distance sensor changes
- **Configurable via UI** — no YAML editing needed; adjust thresholds anytime via *Configure*
- **Alert blueprint** — ready-to-import automation with push notifications + persistent sidebar alerts
- **Lovelace dashboard** — gauge, current readings, 24h and 7-day history graphs, daily statistics
- **Universal** — works with any HA distance sensor, not just ESPHome

---

## Installation

### 1. HACS (recommended)

1. Open HACS → **Integrations** → ⋮ menu → **Custom repositories**
2. Add `https://github.com/royeiror/tinaco-monitor` — category: **Integration**
3. Click **Download** on *Water Tank Monitor*
4. **Restart Home Assistant**

### 2. Manual

Copy the `custom_components/water_tank_monitor/` folder into your HA `config/custom_components/` directory and restart.

---

## Setup

1. **Settings → Devices & Services → Add Integration → Water Tank Monitor**
2. Fill in the form:

   | Field | Default | Notes |
   |-------|---------|-------|
   | Distance sensor | — | Your sensor entity (e.g. `sensor.water_tank_water_distance`) |
   | Min distance | 0.10 m | Distance when tank is **full** |
   | Max distance | 1.20 m | Distance when tank is **empty** |
   | Tank capacity | 700 L | Total volume |
   | Low threshold | 20 % | 🟡 alert fires below this |
   | Critical threshold | 10 % | 🔴 alert fires below this |

3. Click **Submit** — entities appear immediately under the new device.

> All values are editable later via **Configure** on the integration card — no restart needed.

---

## Alert Automation Blueprint

1. **Settings → Automations & Scenes → Blueprints → Import Blueprint**
2. Paste this URL:
   ```
   https://raw.githubusercontent.com/royeiror/tinaco-monitor/main/blueprints/automation/tinaco_monitor/tank_alerts.yaml
   ```
3. Create the automation, select your mobile device and the six sensor entities.

---

## Lovelace Dashboard

1. **Settings → Dashboards → (your dashboard) → Edit → ⋮ → Raw configuration editor**
2. Paste the contents of [`lovelace/dashboard.yaml`](lovelace/dashboard.yaml)

---

## ESPHome Firmware Example

A ready-to-flash ESPHome configuration is included in [`esphome/water_tank.yaml`](esphome/water_tank.yaml).

**Tested hardware:** NodeMCU V2 (ESP8266) + HC-SR04 ultrasonic sensor  
**Default pins:** Trigger → D7, Echo → D6

The firmware reports only raw distance — all calculations happen in HA via this integration.

---

## Formula Reference

```
fill_percent = (max_distance − distance) / (max_distance − min_distance) × 100
volume_liters = fill_percent / 100 × tank_capacity
fill_rate_lph = Δvolume / Δtime  (rolling window of last 10 readings)
```

---

## License

MIT © [royeiror](https://github.com/royeiror)
