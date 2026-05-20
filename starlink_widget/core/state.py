"""Health state machine for widget colors."""

from __future__ import annotations

import math
from enum import Enum
from typing import List, Optional, Tuple

from starlink_widget.core.models import StatusSnapshot


class HealthState(Enum):
    GREEN = "green"
    ORANGE = "orange"
    RED = "red"
    HIDDEN = "hidden"


def shortest_angle_delta(current: float, desired: float) -> float:
    delta = (desired - current) % 360.0
    if delta > 180.0:
        delta -= 360.0
    return delta


def compute_azimuth_delta(
    current: Optional[float], desired: Optional[float]
) -> Optional[float]:
    if current is None or desired is None:
        return None
    try:
        return shortest_angle_delta(float(current), float(desired))
    except (TypeError, ValueError):
        return None


def collect_critical_alerts(snapshot: StatusSnapshot) -> List[str]:
    alerts: List[str] = []
    if snapshot.currently_obstructed or snapshot.fraction_obstructed > 0:
        alerts.append("Obstruction")
    if snapshot.alert_obstructed:
        alerts.append("Obstruction (alerte)")
    if snapshot.alert_slow_ethernet:
        alerts.append("Ethernet lent")
    if snapshot.alert_thermal_shutdown:
        alerts.append("Surchauffe antenne")
    if snapshot.alert_power_thermal_throttle:
        alerts.append("Surchauffe alimentation")
    if snapshot.alert_motors_stuck:
        alerts.append("Moteurs bloqués")
    return alerts


def evaluate_health(snapshot: StatusSnapshot) -> Tuple[HealthState, str]:
    if not snapshot.on_starlink_lan:
        return HealthState.HIDDEN, "Hors réseau Starlink"

    if not snapshot.dish_reachable:
        return HealthState.RED, "ANTENNE HORS LIGNE"

    if not snapshot.internet_ok:
        return HealthState.ORANGE, "SANS INTERNET"

    critical = collect_critical_alerts(snapshot)
    if critical:
        return HealthState.ORANGE, "EN LIGNE — " + ", ".join(critical)

    return HealthState.GREEN, "EN LIGNE"


def format_mbps(bps: Optional[float]) -> str:
    if bps is None or (isinstance(bps, float) and math.isnan(bps)):
        return "—"
    return f"{bps / 1_000_000:.1f}"
