"""Runtime data models."""

from __future__ import annotations

from dataclasses import dataclass

from .api import TuyaOpenApi
from .coordinator import EshtayaIrClimateCoordinator


@dataclass(slots=True)
class EshtayaAccountRuntime:
    """Runtime state for one Tuya cloud project/config entry."""

    api: TuyaOpenApi
    coordinators: dict[str, EshtayaIrClimateCoordinator]
