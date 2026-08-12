# Eshtaya IR Climate

Home Assistant integration for Tuya-based IR air-conditioner thermostats/controllers.

## v0.5.0 — no IR Control Hub subscription

Eshtaya IR Climate does **not** require `IR Control Hub Open Service`.

The integration uses the same `ir_send` datapoint that Smart Life uses on compatible IR thermostats.

### How automatic learning works

1. Use Smart Life normally.
2. Smart Life sends an `ir_send` DP command containing the exact IR payload for the selected A/C state.
3. Eshtaya IR Climate reads the regular IoT Core operation logs and saves that exact payload locally.
4. The next time Home Assistant requests the same mode + temperature + fan state, the integration replays the learned `ir_send` payload through the normal device-control API.
5. Device report logs are also read so physical thermostat changes can update Home Assistant even when the current-state endpoint is slow.

No raw IR payloads from one user's A/C are bundled into the public integration.

## Tuya services

The design uses the normal project/device services already used by the integration, especially IoT Core APIs.

It does **not** call `/v2.0/infrareds/...` endpoints.

## Initial learning

At startup the integration imports up to 100 `ir_send` commands from the previous 24 hours.

You can also press:

**Device → Button → Sync IR library**

to immediately repeat the 24-hour import.

The sensor:

**Learned IR commands**

shows how many exact commands are stored.

## Climate attributes

The main climate entity exposes useful diagnostics:

- `learned_ir_commands`
- `last_learned_ir_key`
- `last_ir_key`
- `last_ir_result`
- `missing_ir_request`
- `last_command_route`

Typical successful control:

```text
last_ir_result: sent
last_ir_key: M0_T25_S3
last_command_route: ir_send:iot03
```

If a combination has not been learned yet:

```text
last_ir_result: missing_learned_command
missing_ir_request: M0_T27_S3
```

Use that combination once in Smart Life and the integration will learn it automatically on the next learning cycle, or press **Sync IR library**.

## Installation

Extract the install ZIP into `/config` so this exists:

```text
/config/custom_components/eshtaya_ir_climate/manifest.json
```

Restart Home Assistant.

For the bundled card, register:

```text
/eshtaya_ir_climate/frontend/eshtaya-ir-climate-card.js?v=0.5.0
```

as a JavaScript Module.

## Security

Never publish your Tuya Access Secret.

The integration does not hard-code a Device ID, virtual-device ID, `head`, or raw IR command from any specific user's air conditioner.
