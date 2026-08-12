"""Datapoint capability parsing and smart profile resolution."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from .api import ProbeResult
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
from .profiles import HWKTWKQ_PROFILE, is_known_ir_thermostat


@dataclass(slots=True)
class DpMeta:
    """Metadata for one Tuya datapoint."""

    code: str
    type: str
    values: dict[str, Any] = field(default_factory=dict)
    writable: bool = False
    readable: bool = False

    @property
    def enum_values(self) -> list[str]:
        raw = self.values.get("range", [])
        return [str(value) for value in raw] if isinstance(raw, list) else []

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
    if isinstance(raw, list):
        return {"range": raw}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"range": parsed}
        except json.JSONDecodeError:
            return {}
    return {}


def _norm(code: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", code.lower()).strip("_")


def _semantic_match(
    available: Iterable[str],
    aliases: Iterable[str],
) -> str | None:
    """Exact first, then normalized token-aware fuzzy match."""
    available = list(available)
    lower = {x.lower(): x for x in available}
    for alias in aliases:
        if alias.lower() in lower:
            return lower[alias.lower()]

    alias_norm = [_norm(a) for a in aliases]
    for code in available:
        ncode = _norm(code)
        for alias in alias_norm:
            if (
                ncode == alias
                or ncode.startswith(alias + "_")
                or ncode.endswith("_" + alias)
            ):
                return code
    return None


@dataclass(slots=True)
class DeviceCapabilities:
    """Resolved capabilities for one IR climate device."""

    dps: dict[str, DpMeta]
    profile: str = "dynamic"
    confidence: int = 0

    @classmethod
    def from_probe(
        cls,
        probe: ProbeResult,
        *,
        trust_manual: bool = False,
    ) -> "DeviceCapabilities":
        dps: dict[str, DpMeta] = {}

        # 1) Live Tuya metadata.
        for row in probe.functions:
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            dps[code] = DpMeta(
                code=code,
                type=str(row.get("type") or row.get("dataType") or ""),
                values=_parse_values(
                    row.get("values")
                    if "values" in row
                    else row.get("specs")
                ),
                writable=True,
                readable=False,
            )

        for row in probe.status_schema:
            code = str(row.get("code") or "").strip()
            if not code:
                continue
            values = _parse_values(
                row.get("values")
                if "values" in row
                else row.get("specs")
            )
            if code in dps:
                dps[code].readable = True
                if values and not dps[code].values:
                    dps[code].values = values
                if not dps[code].type:
                    dps[code].type = str(row.get("type") or "")
            else:
                dps[code] = DpMeta(
                    code=code,
                    type=str(row.get("type") or ""),
                    values=values,
                    writable=False,
                    readable=True,
                )

        # Live status codes are always readable even when Tuya hides the schema.
        for code, value in probe.live_status.items():
            if code in dps:
                dps[code].readable = True
            else:
                inferred_type = (
                    "Boolean" if isinstance(value, bool)
                    else "Integer" if isinstance(value, (int, float))
                    else "Enum" if isinstance(value, str)
                    else ""
                )
                dps[code] = DpMeta(
                    code=code,
                    type=inferred_type,
                    readable=True,
                )

        category = probe.category or str(probe.device.get("category") or "")
        known = is_known_ir_thermostat(probe.device, category)

        # 2) Exact known profile fills any API gaps.
        if known:
            cls._merge_known_profile(dps)
            profile = "hwktwkq_known_profile" if category == "hwktwkq" else "ir_thermostat_product_profile"
        else:
            profile = "dynamic"

        # 3) Semantic alias resolver upgrades hidden writable DPs when their
        # names are clearly climate controls.
        all_codes = list(dps)
        for aliases in (
            POWER_CODES,
            TARGET_TEMP_CODES,
            MODE_CODES,
            FAN_CODES,
        ):
            code = _semantic_match(all_codes, aliases)
            if code and code in dps:
                dps[code].writable = True

        # 4) Manual entry is an explicit user assertion that this is an IR A/C.
        # If Tuya exposes almost no schema, use the safe common profile rather
        # than rejecting the config flow. This makes setup non-blocking while
        # keeping the exact known controller fully supported.
        if trust_manual and not cls._looks_climate(dps):
            cls._merge_known_profile(dps)
            profile = "manual_safe_fallback"

        obj = cls(dps=dps, profile=profile)
        obj.confidence = obj._confidence_score()
        return obj

    @staticmethod
    def _merge_known_profile(dps: dict[str, DpMeta]) -> None:
        for code, (dp_type, values, writable, readable) in HWKTWKQ_PROFILE.items():
            if code in dps:
                dp = dps[code]
                if not dp.type:
                    dp.type = dp_type
                if not dp.values:
                    dp.values = dict(values)
                dp.writable = dp.writable or writable
                dp.readable = dp.readable or readable
            else:
                dps[code] = DpMeta(
                    code=code,
                    type=dp_type,
                    values=dict(values),
                    writable=writable,
                    readable=readable,
                )

    @staticmethod
    def _looks_climate(dps: dict[str, DpMeta]) -> bool:
        codes = list(dps)
        return (
            _semantic_match(codes, POWER_CODES) is not None
            and (
                _semantic_match(codes, TARGET_TEMP_CODES) is not None
                or _semantic_match(codes, MODE_CODES) is not None
            )
        )

    def first(self, candidates: Iterable[str]) -> DpMeta | None:
        code = _semantic_match(self.dps.keys(), candidates)
        return self.dps.get(code) if code else None

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
        return self.power is not None and (
            self.target_temp is not None or self.mode is not None
        )

    def _confidence_score(self) -> int:
        score = 0
        if self.power:
            score += 25
        if self.target_temp:
            score += 25
        if self.mode:
            score += 20
        if self.fan:
            score += 15
        if self.current_temp:
            score += 10
        if self.humidity:
            score += 5
        return min(score, 100)
