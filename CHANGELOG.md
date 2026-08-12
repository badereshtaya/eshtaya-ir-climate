# Changelog

## 0.2.1
- Fixed Tuya products configured in **DP Instruction** mode being incorrectly rejected as unsupported.
- Do not treat a successful-but-empty v1.2 standard specification as authoritative.
- Fall back to `/v1.0/devices/{device_id}/specifications` and `/v1.0/devices/{device_id}/functions`.
- Preserve function metadata when status metadata is synthesized from live DP status.
- Updated project links to `badereshtaya/eshtaya-ir-climate`.

## 0.2.0
- Multi-device Tuya cloud project setup.
- Automatic compatible-device discovery with manual Device ID fallback.
- Current and fallback Tuya API endpoints.
- Added diagnostics with secret redaction.
- Added bundled animated Eshtaya IR Climate dashboard card.
- Card editor, responsive sizing, and Home Assistant 2026.6 entity suggestions.

## 0.1.0
- Initial single-device test integration.
