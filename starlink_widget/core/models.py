"""Data models for widget state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StatusSnapshot:
    dish_reachable: bool = False
    internet_ok: bool = False
    on_starlink_lan: bool = True

    state: str = "UNKNOWN"
    device_id: Optional[str] = None
    hardware_version: Optional[str] = None
    software_version: Optional[str] = None
    disablement_code: Optional[str] = None
    hardware_self_test: Optional[str] = None
    stowed: Optional[bool] = None

    downlink_mbps: Optional[float] = None
    uplink_mbps: Optional[float] = None
    pop_ping_latency_ms: Optional[float] = None
    pop_ping_drop_rate: Optional[float] = None

    currently_obstructed: bool = False
    fraction_obstructed: float = 0.0

    alert_obstructed: bool = False
    alert_slow_ethernet: bool = False
    alert_thermal_shutdown: bool = False
    alert_thermal_throttle: bool = False
    alert_motors_stuck: bool = False
    alert_heating: bool = False
    alert_power_thermal_throttle: bool = False
    alert_mast_not_near_vertical: bool = False
    alert_install_pending: bool = False
    alert_moving_too_fast_for_policy: bool = False

    boresight_azimuth_deg: Optional[float] = None
    boresight_elevation_deg: Optional[float] = None
    desired_azimuth_deg: Optional[float] = None
    desired_elevation_deg: Optional[float] = None
    azimuth_delta_deg: Optional[float] = None

    critical_alerts: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
