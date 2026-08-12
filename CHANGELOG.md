# Changelog

## 0.3.0

- Rebuilt capability discovery around a **multi-source Tuya probe**.
- A successful-but-empty Tuya API response no longer stops fallback discovery.
- Merges metadata/status from:
  - IoT-03 specification
  - v1.2 specification
  - Smart Home legacy specifications
  - IoT-03 device functions
  - Smart Home device functions
  - IoT-03 category functions/status
  - Smart Home category functions
  - device embedded status
  - IoT-03 live status
  - Smart Home live status
  - IoT Core shadow properties
  - IoT Core Things Data Model
- Added exact `hwktwkq` IR Air Thermostat profile verified from Tuya Developer Platform.
- Manual Device ID setup no longer rejects a device merely because Tuya hides DP schema metadata.
- Added semantic/fuzzy DP aliases for other controller variants.
- Added three command routes: IoT-03 commands, Smart Home commands, then IoT Core shadow property issue.
- Added optimistic state retention so an empty/lagging Tuya status endpoint does not make the climate entity unusable.
- Added rich diagnostics with API probe trace and selected compatibility profile.
- Added HACS brand icon and GitHub validation workflows.
- Updated bundled animated card to v0.3.0.

## 0.2.2

- Fixed IoT-03 device functions endpoint.
- Added category fallback and initial known-profile fallback.

## 0.2.1

- Added DP Instruction fallback.

## 0.2.0

- Multi-device discovery and bundled animated dashboard card.

## 0.1.0

- Initial test integration.
