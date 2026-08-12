"""Pure helpers for learning Tuya IR commands from IoT Core logs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

MTS_RE = re.compile(
    r"^(?P<mode>M[^_]+)_T(?P<temp>-?\d+)_S(?P<fan>[^_]+)$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class ParsedIrCommand:
    """One exact IR payload learned from Tuya command logs."""

    key: str
    value: str
    event_time: int
    power: bool | None = None
    mode_raw: str | None = None
    temperature: int | None = None
    fan_raw: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "event_time": self.event_time,
            "power": self.power,
            "mode_raw": self.mode_raw,
            "temperature": self.temperature,
            "fan_raw": self.fan_raw,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ParsedIrCommand":
        return cls(
            key=str(data.get("key") or ""),
            value=str(data.get("value") or ""),
            event_time=int(data.get("event_time") or 0),
            power=data.get("power"),
            mode_raw=(
                str(data["mode_raw"])
                if data.get("mode_raw") is not None
                else None
            ),
            temperature=(
                int(data["temperature"])
                if data.get("temperature") is not None
                else None
            ),
            fan_raw=(
                str(data["fan_raw"])
                if data.get("fan_raw") is not None
                else None
            ),
        )


def _json_object(value: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Return parsed object and the exact string to resend to ir_send."""
    if isinstance(value, dict):
        return value, json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if not isinstance(value, str):
        return None, None

    raw = value.strip()
    if not raw:
        return None, None

    # Tuya operation logs return the DP value as a JSON string. Be tolerant
    # of a second layer of JSON quoting.
    candidate: Any = raw
    for _ in range(2):
        if isinstance(candidate, dict):
            break
        if not isinstance(candidate, str):
            return None, None
        try:
            candidate = json.loads(candidate)
        except json.JSONDecodeError:
            return None, None

    if not isinstance(candidate, dict):
        return None, None

    # Preserve the original object semantically, but normalize whitespace so
    # Home Assistant can persist/replay it consistently.
    normalized = json.dumps(
        candidate,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return candidate, normalized


def parse_ir_send_log(row: dict[str, Any]) -> ParsedIrCommand | None:
    """Parse one operation-log row for DP ir_send."""
    if str(row.get("code") or "").lower() != "ir_send":
        return None

    payload, normalized_value = _json_object(row.get("value"))
    if not payload or not normalized_value:
        return None

    if str(payload.get("control") or "").lower() != "send_ir":
        return None

    key1 = payload.get("key1")
    if not isinstance(key1, dict):
        return None

    key = str(key1.get("key") or "").strip()
    data = key1.get("data")
    if not key or data in (None, ""):
        return None

    event_time = int(row.get("event_time") or 0)
    command = ParsedIrCommand(
        key=key,
        value=normalized_value,
        event_time=event_time,
        power=True,
    )

    if key.lower() in {"power_off", "off", "poweroff"}:
        command.power = False
        return command

    match = MTS_RE.match(key)
    if match:
        command.temperature = int(match.group("temp"))
    return command


def nearest_report_value(
    reports: list[dict[str, Any]],
    code: str | None,
    event_time: int,
    *,
    after_ms: int = 2500,
    before_ms: int = 1500,
) -> Any | None:
    """Find the closest matching report, preferring reports after the command."""
    if not code:
        return None

    matches: list[tuple[int, int, Any]] = []
    for row in reports:
        if str(row.get("code") or "") != code:
            continue
        try:
            ts = int(row.get("event_time") or 0)
        except (TypeError, ValueError):
            continue
        delta = ts - event_time
        if -before_ms <= delta <= after_ms:
            # Prefer a report after the command, then shortest distance.
            priority = 0 if delta >= 0 else 1
            matches.append((priority, abs(delta), row.get("value")))

    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1]))
    return matches[0][2]


def latest_report_before(
    reports: list[dict[str, Any]],
    code: str | None,
    event_time: int,
) -> Any | None:
    """Find latest value for a DP at or before event_time."""
    if not code:
        return None
    candidate: tuple[int, Any] | None = None
    for row in reports:
        if str(row.get("code") or "") != code:
            continue
        try:
            ts = int(row.get("event_time") or 0)
        except (TypeError, ValueError):
            continue
        if ts <= event_time and (candidate is None or ts > candidate[0]):
            candidate = (ts, row.get("value"))
    return candidate[1] if candidate else None


def mts_tokens(key: str) -> tuple[str | None, str | None]:
    """Return mode/fan token portions from an Mx_Tyy_Sz key."""
    match = MTS_RE.match(key)
    if not match:
        return None, None
    return match.group("mode"), "S" + match.group("fan")
