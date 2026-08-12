"""Datapoint capability parsing for Eshtaya IR Climate."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable

from .const import (
    CHILD_LOCK_CODES,
    CURRENT_TEMP_CODES,
    FAN_CODES,
    FAULT_CODES,
    FILTER_LIFE_CODES,
    FILTER_RESET_CODES,
    HUMIDITY_CODES,
    MODE_CODES,
    POWER_CODES,
    RUNTIME_CODES,
    RUNTIME_RESET_CODES,
    STATUS_CODES,
    TARGET_TEMP_CODES,
)


@dataclass(slots=True)
class DpMeta:
    """Metadata for a Tuya datapoint."""

    code: str
    type: str
    values: dict[str, Any] = field(default_factory=dict)
    writable: bool = False
    readable: bool = False

    @property
    def enum_values(self) -> list[str]:
        raw = self.values.get("range", [])
        return [str(v) for v in raw] if isinstance(raw, list) else []

    @property
    def scale(self) -> int:
        try:
            return int(self.values.get("scale", 0))
        except (TypeError, ValueError):
            return 0

    def decode_number(self, raw: Any) -> float | None:
        try:
            return float(raw) / (10 ** self.scale)
        except (TypeError, ValueError):
            return None

    def encode_number(self, value: float) -> int | float:
        scaled = float(value) * (10 ** self.scale)
        if abs(scaled - round(scaled)) < 1e-9:
            return int(round(scaled))
        return scaled

    @property
    def minimum(self) -> float | None:
        return self.decode_number(self.values.get("min"))

    @property
    def maximum(self) -> float | None:
        return self.decode_number(self.values.get("max"))

    @property
    def step(self) -> float | None:
        return self.decode_number(self.values.get("step"))


def _parse_values(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _extract_rows(spec: dict[str, Any], family: str) -> list[dict[str, Any]]:
    aliases = {
        "functions": (
            "functions",
            "function",
            "instruction",
            "instructions",
        ),
        "status": (
            "status",
            "status_set",
            "statuses",
        ),
    }
    for candidate in aliases[family]:
        rows = spec.get(candidate)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


@dataclass(slots=True)
class DeviceCapabilities:
    """Parsed IR climate capabilities."""

    dps: dict[str, DpMeta]

    @classmethod
    def from_specification(cls, spec: dict[str, Any]) -> "DeviceCapabilities":
        dps: dict[str, DpMeta] = {}

        for row in _extract_rows(spec, "functions"):
            code = str(row.get("code", "")).strip()
            if not code:
                continue
            dps[code] = DpMeta(
                code=code,
                type=str(row.get("type", "")),
                values=_parse_values(row.get("values")),
                writable=True,
            )

        for row in _extract_rows(spec, "status"):
            code = str(row.get("code", "")).strip()
            if not code:
                continue
            values = _parse_values(row.get("values"))
            if code in dps:
                dps[code].readable = True
                if values:
                    dps[code].values = values
            else:
                dps[code] = DpMeta(
                    code=code,
                    type=str(row.get("type", "")),
                    values=values,
                    readable=True,
                )

        return cls(dps=dps)

    def first(self, candidates: Iterable[str]) -> DpMeta | None:
        for code in candidates:
            if code in self.dps:
                return self.dps[code]
        return None

    @property
    def power(self) -> DpMeta | None:
        return self.first(POWER_CODES)

    @property
    def target_temp(self) -> DpMeta | None:
        return self.first(TARGET_TEMP_CODES)

    @property
    def current_temp(self) -> DpMeta | None:
        return self.first(CURRENT_TEMP_CODES)

    @property
    def mode(self) -> DpMeta | None:
        return self.first(MODE_CODES)

    @property
    def fan(self) -> DpMeta | None:
        return self.first(FAN_CODES)

    @property
    def humidity(self) -> DpMeta | None:
        return self.first(HUMIDITY_CODES)

    @property
    def filter_life(self) -> DpMeta | None:
        return self.first(FILTER_LIFE_CODES)

    @property
    def runtime(self) -> DpMeta | None:
        return self.first(RUNTIME_CODES)

    @property
    def fault(self) -> DpMeta | None:
        return self.first(FAULT_CODES)

    @property
    def status(self) -> DpMeta | None:
        return self.first(STATUS_CODES)

    @property
    def child_lock(self) -> DpMeta | None:
        return self.first(CHILD_LOCK_CODES)

    @property
    def filter_reset(self) -> DpMeta | None:
        return self.first(FILTER_RESET_CODES)

    @property
    def runtime_reset(self) -> DpMeta | None:
        return self.first(RUNTIME_RESET_CODES)

    @property
    def climate_compatible(self) -> bool:
        """Return whether this looks like an IR A/C controller."""
        return (
            self.power is not None
            and self.power.writable
            and (
                (self.target_temp is not None and self.target_temp.writable)
                or (self.mode is not None and self.mode.writable)
            )
        )
