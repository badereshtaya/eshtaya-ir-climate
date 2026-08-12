"""Persistent automatic IR library learned from Tuya IoT Core logs."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .ir_codec import (
    ParsedIrCommand,
    latest_report_before,
    mts_tokens,
    nearest_report_value,
    parse_ir_send_log,
)

_LOGGER = logging.getLogger(__name__)
STORAGE_VERSION = 1

# Verified mappings for the hwktwkq controller family. These are state/key
# labels only; no user's IR payloads are bundled into the integration.
KNOWN_MODE_TOKENS = {
    "cold": "M0",
}
KNOWN_FAN_TOKENS = {
    "auto": "S0",
    "low": "S1",
    "middle": "S2",
    "high": "S3",
}


class IrCommandLibrary:
    """Store exact ir_send payloads and semantic mappings per device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_id: str,
        *,
        known_profile: bool,
    ) -> None:
        safe_key = "".join(
            ch if ch.isalnum() else "_"
            for ch in device_id
        )
        self._store = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.ir_library.{safe_key}",
        )
        self.device_id = device_id
        self.known_profile = known_profile

        self.commands: dict[str, ParsedIrCommand] = {}
        self.mode_tokens: dict[str, str] = (
            dict(KNOWN_MODE_TOKENS) if known_profile else {}
        )
        self.fan_tokens: dict[str, str] = (
            dict(KNOWN_FAN_TOKENS) if known_profile else {}
        )
        self.last_operation_event_time = 0
        self.last_learned_key: str | None = None
        self.last_missing_request: str | None = None

    async def async_load(self) -> None:
        data = await self._store.async_load()
        if not isinstance(data, dict):
            return

        raw_commands = data.get("commands")
        if isinstance(raw_commands, dict):
            for key, value in raw_commands.items():
                if isinstance(value, dict):
                    command = ParsedIrCommand.from_dict(value)
                    if command.key and command.value:
                        self.commands[str(key)] = command

        if isinstance(data.get("mode_tokens"), dict):
            self.mode_tokens.update(
                {
                    str(key): str(value)
                    for key, value in data["mode_tokens"].items()
                    if key and value
                }
            )
        if isinstance(data.get("fan_tokens"), dict):
            self.fan_tokens.update(
                {
                    str(key): str(value)
                    for key, value in data["fan_tokens"].items()
                    if key and value
                }
            )

        self.last_operation_event_time = int(
            data.get("last_operation_event_time") or 0
        )
        self.last_learned_key = (
            str(data["last_learned_key"])
            if data.get("last_learned_key")
            else None
        )

    async def async_save(self) -> None:
        await self._store.async_save(
            {
                "commands": {
                    key: command.as_dict()
                    for key, command in self.commands.items()
                },
                "mode_tokens": dict(self.mode_tokens),
                "fan_tokens": dict(self.fan_tokens),
                "last_operation_event_time": self.last_operation_event_time,
                "last_learned_key": self.last_learned_key,
            }
        )

    @property
    def count(self) -> int:
        return len(self.commands)

    def _state_value(
        self,
        reports: list[dict[str, Any]],
        code: str | None,
        event_time: int,
        fallback: Any,
    ) -> Any:
        value = nearest_report_value(reports, code, event_time)
        if value is not None:
            return value
        value = latest_report_before(reports, code, event_time)
        if value is not None:
            return value
        return fallback

    async def async_learn(
        self,
        operation_logs: list[dict[str, Any]],
        report_logs: list[dict[str, Any]],
        *,
        mode_code: str | None,
        fan_code: str | None,
        target_code: str | None,
        power_code: str | None,
        current_state: dict[str, Any],
    ) -> int:
        """Learn exact ir_send payloads and correlate them with DP state."""
        changed = False
        learned_now = 0

        # Process old -> new so later duplicate keys naturally win.
        rows = sorted(
            operation_logs,
            key=lambda row: int(row.get("event_time") or 0),
        )

        for row in rows:
            command = parse_ir_send_log(row)
            if command is None:
                continue

            self.last_operation_event_time = max(
                self.last_operation_event_time,
                command.event_time,
            )

            if command.power is not False:
                mode_value = self._state_value(
                    report_logs,
                    mode_code,
                    command.event_time,
                    current_state.get(mode_code) if mode_code else None,
                )
                fan_value = self._state_value(
                    report_logs,
                    fan_code,
                    command.event_time,
                    current_state.get(fan_code) if fan_code else None,
                )
                target_value = self._state_value(
                    report_logs,
                    target_code,
                    command.event_time,
                    current_state.get(target_code) if target_code else None,
                )
                power_value = self._state_value(
                    report_logs,
                    power_code,
                    command.event_time,
                    current_state.get(power_code) if power_code else None,
                )

                if mode_value is not None:
                    command.mode_raw = str(mode_value)
                if fan_value is not None:
                    command.fan_raw = str(fan_value)
                if command.temperature is None and target_value is not None:
                    try:
                        command.temperature = int(round(float(target_value)))
                    except (TypeError, ValueError):
                        pass
                if power_value is not None:
                    if isinstance(power_value, bool):
                        command.power = power_value
                    else:
                        text = str(power_value).strip().lower()
                        if text in {"true", "1", "on", "open", "opened"}:
                            command.power = True
                        elif text in {
                            "false", "0", "off", "close", "closed", "switch",
                        }:
                            command.power = False

                mode_token, fan_token = mts_tokens(command.key)
                if mode_token and command.mode_raw:
                    self.mode_tokens[command.mode_raw] = mode_token
                if fan_token and command.fan_raw:
                    self.fan_tokens[command.fan_raw] = fan_token

            old = self.commands.get(command.key)
            if old is None or old.value != command.value or old.as_dict() != command.as_dict():
                self.commands[command.key] = command
                self.last_learned_key = command.key
                changed = True
                learned_now += 1

        if changed:
            await self.async_save()
            _LOGGER.info(
                "Learned %s IR command(s) for ...%s; library now has %s",
                learned_now,
                self.device_id[-6:],
                self.count,
            )
        return learned_now

    def find(
        self,
        *,
        power: bool,
        mode_raw: str | None,
        temperature: float | None,
        fan_raw: str | None,
    ) -> ParsedIrCommand | None:
        """Find an exact learned command for the requested complete A/C state."""
        if not power:
            for key in ("power_off", "off", "poweroff"):
                if key in self.commands:
                    return self.commands[key]
            for command in self.commands.values():
                if command.power is False:
                    return command
            self.last_missing_request = "power_off"
            return None

        temp_int = int(round(temperature)) if temperature is not None else None

        # First use semantic metadata learned from correlated report logs.
        candidates = [
            command
            for command in self.commands.values()
            if command.power is not False
            and (mode_raw is None or command.mode_raw in (None, mode_raw))
            and (temp_int is None or command.temperature == temp_int)
            and (fan_raw is None or command.fan_raw in (None, fan_raw))
        ]
        fully_matching = [
            command
            for command in candidates
            if (mode_raw is None or command.mode_raw == mode_raw)
            and (fan_raw is None or command.fan_raw == fan_raw)
        ]
        if fully_matching:
            return max(fully_matching, key=lambda item: item.event_time)

        # Then construct the exact Tuya key from mappings we learned.
        mode_token = self.mode_tokens.get(str(mode_raw)) if mode_raw else None
        fan_token = self.fan_tokens.get(str(fan_raw)) if fan_raw else None
        if mode_token and fan_token and temp_int is not None:
            key = f"{mode_token}_T{temp_int}_{fan_token}"
            if key in self.commands:
                return self.commands[key]
            self.last_missing_request = key
        else:
            self.last_missing_request = (
                f"mode={mode_raw},temp={temp_int},fan={fan_raw}"
            )
        return None

    def diagnostics(self) -> dict[str, Any]:
        """Return safe library metadata without raw IR payload contents."""
        return {
            "count": self.count,
            "mode_tokens": dict(self.mode_tokens),
            "fan_tokens": dict(self.fan_tokens),
            "last_operation_event_time": self.last_operation_event_time,
            "last_learned_key": self.last_learned_key,
            "last_missing_request": self.last_missing_request,
            "keys": sorted(self.commands),
        }
