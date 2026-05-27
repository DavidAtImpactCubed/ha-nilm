from __future__ import annotations

from typing import Any, Optional


POWER_UNITS_WATTS = {"W", "kW"}


def normalize_power_to_watts(raw_value: Any, unit: Optional[str]) -> float:
    value = float(raw_value)
    normalized_unit = str(unit or "").strip()
    if normalized_unit == "kW":
        return value * 1000.0
    return value


def is_supported_power_unit(unit: Optional[str]) -> bool:
    return str(unit or "").strip() in POWER_UNITS_WATTS
