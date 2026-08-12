# Eshtaya IR Climate

**Eshtaya IR Climate** is a Home Assistant custom integration for Tuya-based infrared air-conditioner controllers.

It dynamically reads each device's Tuya datapoint specification instead of hard-coding one Product ID, and it includes an animated custom dashboard card.

## v0.2.0

### Integration

- Enter Tuya Cloud credentials once.
- Automatically discovers linked devices when the Tuya project permits device-list access.
- Checks the Tuya specification and only offers compatible IR climate devices.
- Select one or multiple compatible A/C controllers.
- Manual Device ID fallback if Tuya does not permit discovery.
- Dynamic climate capability mapping.
- Cloud polling every 30 seconds.
- Diagnostics for sharing unknown DP schemas without exposing the Tuya Access Secret.

Common supported datapoint aliases include:

- Power: `infrared_switch`, `switch`, `switch_1`, `power`
- Target temperature: `target_temp`, `temp_set`, `temp_set_f`, `temperature_set`
- Current temperature: `temp_current`, `temp_current_f`, `temperature_current`
- HVAC mode: `mode`, `work_mode`
- Fan: `fan_level`, `fan_speed`, `windspeed`, `wind_speed`
- Humidity: `humidity_current`, `humidity`

Optional entities are created when the device exposes them:

- Current temperature sensor
- Humidity sensor
- Filter-life sensor
- Runtime sensor
- Status sensor
- Fault sensor
- Child-lock switch
- Filter reset button
- Runtime reset button

### Bundled animated dashboard card

The integration ships `Eshtaya IR Climate Card` inside the same package.

The card provides:

- Animated mode-aware background
- Animated airflow effect while the A/C is running
- Dynamic cooling/heating/dry/fan colors
- Large target-temperature dial
- Plus/minus controls and a temperature slider
- Room-temperature and humidity display
- HVAC mode controls
- Fan-speed controls with rotating fan animation
- Responsive layout
- Reduced-motion accessibility support
- Visual card editor
- Home Assistant 2026.6+ card-picker entity suggestions

## Manual installation

Extract the package so this directory exists:

```text
/config/custom_components/eshtaya_ir_climate/
```

Restart Home Assistant.

Then:

**Settings → Devices & services → Add Integration → Eshtaya IR Climate**

Enter:

- Tuya Access ID / Client ID
- Tuya Access Secret / Client Secret
- Tuya Data Center

For the development device used for this project, the data center is **Central Europe**.

If device discovery is available, select one or more compatible A/C controllers. Otherwise enter a Device ID manually.

## Add the animated card

The integration serves the bundled JavaScript file at:

```text
/eshtaya_ir_climate/frontend/eshtaya-ir-climate-card.js
```

Register it once in:

**Settings → Dashboards → Resources → Add resource**

URL:

```text
/eshtaya_ir_climate/frontend/eshtaya-ir-climate-card.js?v=0.2.0
```

Resource type:

```text
JavaScript Module
```

Refresh the browser.

You can then add the card from the card picker, or use YAML:

```yaml
type: custom:eshtaya-ir-climate-card
entity: climate.living_room_ac
name: Living Room
show_current_temperature: true
show_humidity: true
show_fan: true
```

The card is deliberately usable with normal Home Assistant `climate` entities too, although Eshtaya IR Climate entities expose the intended capability set.

## HACS

This repository is structured as a HACS **Integration** repository. All runtime files, including the bundled dashboard-card JavaScript, live inside:

```text
custom_components/eshtaya_ir_climate/
```

That keeps one HACS installation responsible for both the backend integration and its bundled UI asset. The dashboard resource still needs to be registered in Home Assistant once.

Before submitting to the default HACS repository, test multiple Tuya IR controller schemas and create GitHub releases.

## Security

Never publish your Tuya Access Secret. The config flow stores it in the Home Assistant config entry. Diagnostics redact the secret.

## First confirmed development schema

The initial development device is a Tuya IR Air Thermostat / Smart Air Conditioner Controller exposing:

- `infrared_switch`
- `temp_current`
- `target_temp`
- `mode`: `cold`, `warm`, `auto`, `air`, `dehumidify`
- `fan_level`: `auto`, `low`, `middle`, `high`
- `humidity_current`
- `filter_life`
- `runtime`
- `status`
- `fault`
- `child_lock`
- `filter_reset`
- `runtime_total_reset`
