# Eshtaya IR Climate

A Home Assistant custom integration for Tuya-based infrared air-conditioner controllers.

## Why v0.3.0 is different

Tuya can expose the same device through several API families, and some products return a successful but empty **standard** specification even though the device has working original DPs. Eshtaya IR Climate therefore does not depend on one specification endpoint.

It probes and merges several Tuya surfaces, including classic IoT-03, Smart Home APIs, live device status, IoT Core shadow properties, category metadata, and the Things Data Model. If Tuya still hides metadata for a manually selected controller, the integration uses a conservative compatibility profile rather than rejecting setup.

The `hwktwkq` IR Air Thermostat / Smart Air Conditioner Controller family has a dedicated built-in profile.

## Installation

Extract so this exists:

```text
/config/custom_components/eshtaya_ir_climate/
```

Restart Home Assistant, then:

**Settings → Devices & services → Add Integration → Eshtaya IR Climate**

Enter your Tuya Cloud:

- Access ID / Client ID
- Access Secret / Client Secret
- Data Center

If automatic discovery cannot identify your controller with high confidence, enter its Device ID manually. A hidden standard DP schema will no longer cause an "unsupported climate schema" rejection.

## Bundled animated card

Register this once under:

**Settings → Dashboards → Resources**

URL:

```text
/eshtaya_ir_climate/frontend/eshtaya-ir-climate-card.js?v=0.3.0
```

Type:

```text
JavaScript Module
```

Then use:

```yaml
type: custom:eshtaya-ir-climate-card
entity: climate.living_room_ac
show_current_temperature: true
show_humidity: true
show_fan: true
```

## Diagnostics

If a new Tuya model behaves differently:

**Settings → Devices & services → Eshtaya IR Climate → Download diagnostics**

Diagnostics include the selected compatibility profile, DP metadata, live status and which Tuya API surfaces returned data. Secrets, local keys and identifying network/account fields are redacted.

## HACS

The repository includes:

- `custom_components/eshtaya_ir_climate/brand/icon.png`
- HACS validation workflow
- Hassfest workflow
- `hacs.json`

Repository:

`badereshtaya/eshtaya-ir-climate`

## Security

Never publish your Tuya Access Secret. It is stored in the Home Assistant config entry and redacted from diagnostics.
