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


def is_obstructed(snapshot: StatusSnapshot) -> bool:
    """Obstruction gRPC ou perte ping élevée (avec hystérésis)."""
    return snapshot.currently_obstructed is True


PING_DROP_OBSTRUCT_ENTER_PCT = 60.0
PING_DROP_OBSTRUCT_EXIT_PCT = 30.0


class PingDropObstructionTracker:
    """Obstruction déduite de la perte ping : >60 % entre, <30 % sort."""

    def __init__(
        self,
        *,
        enter_pct: float = PING_DROP_OBSTRUCT_ENTER_PCT,
        exit_pct: float = PING_DROP_OBSTRUCT_EXIT_PCT,
    ) -> None:
        self.enter_pct = enter_pct
        self.exit_pct = exit_pct
        self._active = False

    def update(self, drop_rate_pct: Optional[float]) -> bool:
        if drop_rate_pct is None:
            return self._active
        if self._active:
            if drop_rate_pct < self.exit_pct:
                self._active = False
        elif drop_rate_pct > self.enter_pct:
            self._active = True
        return self._active


def apply_ping_drop_obstruction(
    snapshot: StatusSnapshot, tracker: PingDropObstructionTracker
) -> None:
    """Fusionne obstruction gRPC et perte ping (hystérésis)."""
    ping_obs = tracker.update(snapshot.pop_ping_drop_rate)
    snapshot.currently_obstructed = (
        snapshot.currently_obstructed is True or ping_obs
    )


def resolve_internet_ok(snapshot: StatusSnapshot, ping_ok: bool) -> bool:
    """Internet OK si ping réussi ou si le terminal Starlink est connecté."""
    if not snapshot.dish_reachable:
        return False
    if ping_ok:
        return True

    state = (snapshot.state or "").upper()
    if state == "CONNECTED":
        return True

    if snapshot.pop_ping_latency_ms is not None:
        return True

    return False


def collect_critical_alerts(snapshot: StatusSnapshot) -> List[str]:
    alerts: List[str] = []
    if is_obstructed(snapshot):
        alerts.append("Obstruction")
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

    critical = collect_critical_alerts(snapshot)

    if not snapshot.internet_ok:
        if critical:
            return HealthState.ORANGE, "EN LIGNE — " + ", ".join(critical)
        if (snapshot.state or "").upper() == "CONNECTED":
            return HealthState.GREEN, "EN LIGNE"
        return HealthState.ORANGE, "SANS INTERNET"

    if critical:
        return HealthState.ORANGE, "EN LIGNE — " + ", ".join(critical)

    return HealthState.GREEN, "EN LIGNE"


def format_mbps(bps: Optional[float]) -> str:
    if bps is None or (isinstance(bps, float) and math.isnan(bps)):
        return "—"
    return f"{bps / 1_000_000:.1f}"
