# Tinaco Monitor

A [Home Assistant](https://www.home-assistant.io/) custom integration that turns any numeric distance sensor into a full water-tank monitoring system — percentage, volume, fill rate, and configurable alerts.

Built for use with an **ESP8266 + HC-SR04 ultrasonic sensor** flashed with ESPHome, but works with any HA distance sensor entity.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue)](https://www.home-assistant.io/)

---

## Features

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.tinaco_monitor_porcentaje_de_llenado` | Sensor | Fill level 0–100 % |
| `sensor.tinaco_monitor_volumen_de_agua` | Sensor | Volume in liters |
| `sensor.tinaco_monitor_tasa_de_llenado` | Sensor | Fill/drain rate in L/h |
| `binary_sensor.tinaco_monitor_nivel_bajo` | Binary sensor | ON when below low threshold |
| `binary_sensor.tinaco_monitor_nivel_critico` | Binary sensor | ON when below critical threshold |
| `binary_sensor.tinaco_monitor_tinaco_lleno` | Binary sensor | ON when tank ≥ 95 % full |

- **Event-driven** — no polling, updates instantly when the distance sensor changes
- **Configurable via UI** — no YAML editing needed; adjust thresholds anytime via *Configure*
- **Alert blueprint** — ready-to-import automation with push notifications + persistent sidebar alerts
- **Lovelace dashboard** — gauge, current readings, 24h and 7-day history graphs, daily statistics

---

## Installation

### 1. HACS (recommended)

1. Open HACS → **Integrations** → ⋮ menu → **Custom repositories**
2. Add `https://github.com/royeiror/tinaco-monitor` — category: **Integration**
3. Click **Download** on *Tinaco Monitor*
4. **Restart Home Assistant**

### 2. Manual

Copy the `custom_components/tinaco_monitor/` folder into your HA `config/custom_components/` directory and restart.

---

## Setup

1. **Settings → Devices & Services → Add Integration → Tinaco Monitor**
2. Fill in the form:

   | Field | Default | Notes |
   |-------|---------|-------|
   | Distance sensor | — | Your ESPHome entity (e.g. `sensor.tinaco_distancia_al_agua`) |
   | Min distance | 0.10 m | Distance when tank is **full** |
   | Max distance | 1.20 m | Distance when tank is **empty** |
   | Tank capacity | 700 L | Total volume |
   | Low threshold | 20 % | 🟡 alert fires below this |
   | Critical threshold | 10 % | 🔴 alert fires below this |

3. Click **Submit** — entities appear immediately under the new device.

> You can change all values later via **Configure** on the integration card — no restart needed.

---

## Alert Automation Blueprint

1. **Settings → Automations & Scenes → Blueprints → Import Blueprint**
2. Paste this URL:
   ```
   https://raw.githubusercontent.com/royeiror/tinaco-monitor/main/blueprints/automation/tinaco_monitor/tank_alerts.yaml
   ```
3. Create the automation, select your mobile device and the six entities.

---

## Lovelace Dashboard

1. **Settings → Dashboards → Add Dashboard** (or open an existing one)
2. Switch to **Edit** mode → ⋮ → **Raw configuration editor**
3. Paste the contents of [`lovelace/dashboard.yaml`](lovelace/dashboard.yaml)

---

## ESPHome Firmware

A ready-to-flash ESPHome configuration is included in [`esphome/tinaco.yaml`](esphome/tinaco.yaml).

**Hardware:** NodeMCU V2 (ESP8266) + HC-SR04 ultrasonic sensor  
**Pins:** Trigger → D7, Echo → D6

The firmware reports only raw distance — all calculations happen in HA.

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
