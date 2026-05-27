"""Champs affichables sur le widget (alignés sur les données diagnostic Starlink)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from starlink_widget.core.models import StatusSnapshot

# (value, unit) ou None si rien à afficher
FieldFormatter = Callable[[StatusSnapshot], Optional[Tuple[str, str]]]


@dataclass(frozen=True)
class DisplayField:
    key: str
    label: str
    category: str
    default: bool = False


def _fmt_bool(val: Optional[bool]) -> Optional[Tuple[str, str]]:
    if val is None:
        return None
    return ("Oui", "") if val else ("Non", "")


def _fmt_float(val: Optional[float], unit: str = "", decimals: int = 1) -> Optional[Tuple[str, str]]:
    if val is None:
        return None
    return (f"{val:.{decimals}f}", unit)


def _fmt_str(val: Optional[str]) -> Optional[Tuple[str, str]]:
    if not val:
        return None
    return (str(val), "")


DISPLAY_FIELDS: List[DisplayField] = [
    # En-tête / résumé
    DisplayField("connection_status", "Statut connexion", "Général", True),
    DisplayField("alerts_summary", "Résumé alertes actives", "Général", True),
    # Appareil
    DisplayField("device_id", "ID terminal", "Appareil", False),
    DisplayField("hardware_version", "Version matériel", "Appareil", False),
    DisplayField("software_version", "Version logiciel", "Appareil", True),
    DisplayField("state", "État antenne", "Appareil", False),
    DisplayField("disablement_code", "Code désactivation", "Appareil", False),
    DisplayField("hardware_self_test", "Auto-test matériel", "Appareil", False),
    DisplayField("stowed", "Rangé (stowed)", "Appareil", False),
    # Débits & réseau
    DisplayField("downlink", "Débit descendant", "Débits", True),
    DisplayField("uplink", "Débit montant", "Débits", True),
    DisplayField("pop_ping_latency", "Latence ping", "Débits", True),
    DisplayField("pop_ping_drop_rate", "Perte ping", "Débits", False),
    # Alignement
    DisplayField("azimuth_delta", "Écart azimut Δ", "Alignement", True),
    DisplayField("boresight_azimuth", "Azimut actuel", "Alignement", False),
    DisplayField("boresight_elevation", "Élévation actuelle", "Alignement", False),
    DisplayField("desired_azimuth", "Azimut cible", "Alignement", False),
    DisplayField("desired_elevation", "Élévation cible", "Alignement", False),
    # Alertes (diagnostic JSON)
    DisplayField("obstructed", "Obstrué", "Alertes", False),
    DisplayField("dish_is_heating", "Chauffage antenne", "Alertes", False),
    DisplayField("dish_thermal_throttle", "Throttle thermique", "Alertes", False),
    DisplayField("dish_thermal_shutdown", "Arrêt thermique", "Alertes", False),
    DisplayField("power_supply_thermal_throttle", "Throttle alimentation", "Alertes", False),
    DisplayField("motors_stuck", "Moteurs bloqués", "Alertes", False),
    DisplayField("mast_not_near_vertical", "Mât pas vertical", "Alertes", False),
    DisplayField("slow_ethernet_speeds", "Ethernet lent", "Alertes", False),
    DisplayField("software_install_pending", "MAJ en attente", "Alertes", False),
    DisplayField("moving_too_fast_for_policy", "Déplacement trop rapide", "Alertes", False),
]

HEADER_KEYS = frozenset({"connection_status", "alerts_summary"})

FIELD_BY_KEY: Dict[str, DisplayField] = {f.key: f for f in DISPLAY_FIELDS}

DEFAULT_VISIBLE_KEYS: List[str] = [f.key for f in DISPLAY_FIELDS if f.default]


def _formatters() -> Dict[str, FieldFormatter]:
    return {
        "device_id": lambda s: _fmt_str(s.device_id),
        "hardware_version": lambda s: _fmt_str(s.hardware_version),
        "software_version": lambda s: _fmt_str(s.software_version),
        "state": lambda s: _fmt_str(s.state),
        "disablement_code": lambda s: _fmt_str(s.disablement_code),
        "hardware_self_test": lambda s: _fmt_str(s.hardware_self_test),
        "stowed": lambda s: _fmt_bool(s.stowed),
        "downlink": lambda s: _fmt_float(s.downlink_mbps, "Mbps"),
        "uplink": lambda s: _fmt_float(s.uplink_mbps, "Mbps"),
        "pop_ping_latency": lambda s: _fmt_float(s.pop_ping_latency_ms, "ms", 0),
        "pop_ping_drop_rate": lambda s: _fmt_float(s.pop_ping_drop_rate, "%", 2),
        "azimuth_delta": lambda s: _fmt_float(s.azimuth_delta_deg, "°"),
        "boresight_azimuth": lambda s: _fmt_float(s.boresight_azimuth_deg, "°"),
        "boresight_elevation": lambda s: _fmt_float(s.boresight_elevation_deg, "°"),
        "desired_azimuth": lambda s: _fmt_float(s.desired_azimuth_deg, "°"),
        "desired_elevation": lambda s: _fmt_float(s.desired_elevation_deg, "°"),
        "obstructed": lambda s: _fmt_bool(s.currently_obstructed),
        "dish_is_heating": lambda s: _fmt_bool(s.alert_heating),
        "dish_thermal_throttle": lambda s: _fmt_bool(s.alert_thermal_throttle),
        "dish_thermal_shutdown": lambda s: _fmt_bool(s.alert_thermal_shutdown),
        "power_supply_thermal_throttle": lambda s: _fmt_bool(
            s.alert_power_thermal_throttle
        ),
        "motors_stuck": lambda s: _fmt_bool(s.alert_motors_stuck),
        "mast_not_near_vertical": lambda s: _fmt_bool(s.alert_mast_not_near_vertical),
        "slow_ethernet_speeds": lambda s: _fmt_bool(s.alert_slow_ethernet),
        "software_install_pending": lambda s: _fmt_bool(s.alert_install_pending),
        "moving_too_fast_for_policy": lambda s: _fmt_bool(
            s.alert_moving_too_fast_for_policy
        ),
    }


_FORMATTERS: Optional[Dict[str, FieldFormatter]] = None


def format_field(snapshot: StatusSnapshot, key: str) -> Optional[Tuple[str, str]]:
    global _FORMATTERS
    if _FORMATTERS is None:
        _FORMATTERS = _formatters()
    fn = _FORMATTERS.get(key)
    if fn is None:
        return None
    return fn(snapshot)


def fields_by_category() -> Dict[str, List[DisplayField]]:
    groups: Dict[str, List[DisplayField]] = {}
    for field in DISPLAY_FIELDS:
        groups.setdefault(field.category, []).append(field)
    return groups


GRAPHABLE_KEYS = frozenset(
    {
        "downlink",
        "uplink",
        "pop_ping_latency",
        "pop_ping_drop_rate",
        "azimuth_delta",
        "boresight_azimuth",
        "boresight_elevation",
        "desired_azimuth",
        "desired_elevation",
    }
)


def supports_graph(key: str) -> bool:
    return key in GRAPHABLE_KEYS


def graph_footer_label(key: str) -> str:
    """Sous-titre du graphique (carte pleine largeur)."""
    if key == "pop_ping_latency":
        return "dernière minute"
    if key == "pop_ping_drop_rate":
        return "dernière minute"
    return "dernière minute"


def numeric_sample(snapshot: StatusSnapshot, key: str) -> Optional[float]:
    """Valeur numérique pour l'historique / sparkline."""
    if not supports_graph(key):
        return None
    mapping = {
        "downlink": snapshot.downlink_mbps,
        "uplink": snapshot.uplink_mbps,
        "pop_ping_latency": snapshot.pop_ping_latency_ms,
        "pop_ping_drop_rate": snapshot.pop_ping_drop_rate,
        "azimuth_delta": snapshot.azimuth_delta_deg,
        "boresight_azimuth": snapshot.boresight_azimuth_deg,
        "boresight_elevation": snapshot.boresight_elevation_deg,
        "desired_azimuth": snapshot.desired_azimuth_deg,
        "desired_elevation": snapshot.desired_elevation_deg,
    }
    val = mapping.get(key)
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None
