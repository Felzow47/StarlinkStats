"""gRPC client wrapper for Starlink dish status."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

# Vendored starlink_grpc from sparky8512/starlink-grpc-tools
_vendor = Path(__file__).resolve().parents[1] / "vendor"
if str(_vendor) not in sys.path:
    sys.path.insert(0, str(_vendor))

import starlink_grpc  # noqa: E402
from starlink_grpc import ChannelContext, GrpcError  # noqa: E402

from starlink_widget.core.config import AppConfig
from starlink_widget.core.models import StatusSnapshot
from starlink_widget.core.state import compute_azimuth_delta


class StarlinkClient:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._context: Optional[ChannelContext] = None

    def _get_context(self) -> ChannelContext:
        if self._context is None:
            self._context = ChannelContext(target=self.config.starlink_target)
        return self._context

    def close(self) -> None:
        if self._context is not None:
            self._context.close()
            self._context = None

    def fetch_status(self) -> StatusSnapshot:
        snapshot = StatusSnapshot()
        try:
            ctx = self._get_context()
            status = starlink_grpc.get_status(ctx)
            status_dict, _, alert_dict = starlink_grpc.status_data(ctx)

            snapshot.dish_reachable = True
            snapshot.state = status_dict.get("state") or "UNKNOWN"
            device_info = getattr(status, "device_info", None)
            if device_info is not None:
                snapshot.device_id = getattr(device_info, "id", None)
                snapshot.hardware_version = getattr(
                    device_info, "hardware_version", None
                )
                snapshot.software_version = getattr(
                    device_info, "software_version", None
                )
                snapshot.hardware_self_test = getattr(
                    device_info, "hardware_self_test", None
                )

            device_state = getattr(status, "device_state", None)
            snapshot.stowed = _get_attr_bool(status, "stowed") or _get_attr_bool(
                device_state, "stowed"
            )
            snapshot.disablement_code = _str_or_none(
                getattr(status, "disablement_code", None)
                or getattr(device_state, "disablement_code", None)
            )

            dl = getattr(status, "downlink_throughput_bps", None) or status_dict.get(
                "downlink_throughput_bps"
            )
            ul = getattr(status, "uplink_throughput_bps", None) or status_dict.get(
                "uplink_throughput_bps"
            )
            if dl is not None:
                snapshot.downlink_mbps = dl / 1_000_000
            if ul is not None:
                snapshot.uplink_mbps = ul / 1_000_000

            lat = getattr(status, "pop_ping_latency_ms", None) or status_dict.get(
                "pop_ping_latency_ms"
            )
            drop = getattr(status, "pop_ping_drop_rate", None) or status_dict.get(
                "pop_ping_drop_rate"
            )
            snapshot.pop_ping_latency_ms = _float_or_none(lat)
            snapshot.pop_ping_drop_rate = _float_or_none(drop)
            if snapshot.pop_ping_drop_rate is not None:
                snapshot.pop_ping_drop_rate *= 100.0

            snapshot.currently_obstructed = (
                status_dict.get("currently_obstructed") is True
            )
            frac = status_dict.get("fraction_obstructed")
            snapshot.fraction_obstructed = float(frac) if frac else 0.0

            snapshot.alert_slow_ethernet = alert_dict.get(
                "alert_slow_ethernet_speeds", False
            )
            snapshot.alert_thermal_shutdown = alert_dict.get(
                "alert_thermal_shutdown", False
            )
            snapshot.alert_motors_stuck = alert_dict.get("alert_motors_stuck", False)
            snapshot.alert_heating = alert_dict.get("alert_is_heating", False)
            snapshot.alert_power_thermal_throttle = alert_dict.get(
                "alert_power_supply_thermal_throttle", False
            )
            snapshot.alert_obstructed = alert_dict.get("alert_obstructed", False)
            snapshot.alert_thermal_throttle = alert_dict.get(
                "alert_thermal_throttle", False
            )
            snapshot.alert_mast_not_near_vertical = alert_dict.get(
                "alert_mast_not_near_vertical", False
            )
            snapshot.alert_install_pending = alert_dict.get(
                "alert_install_pending", False
            )
            snapshot.alert_moving_too_fast_for_policy = alert_dict.get(
                "alert_moving_too_fast_for_policy", False
            )

            snapshot.boresight_azimuth_deg = _get_attr_float(
                status, "boresight_azimuth_deg"
            ) or _float_or_none(status_dict.get("direction_azimuth"))
            snapshot.boresight_elevation_deg = _get_attr_float(
                status, "boresight_elevation_deg"
            ) or _float_or_none(status_dict.get("direction_elevation"))

            alignment = getattr(status, "alignment_stats", None)
            if alignment is not None:
                snapshot.boresight_azimuth_deg = (
                    snapshot.boresight_azimuth_deg
                    or _get_attr_float(alignment, "boresight_azimuth_deg")
                )
                snapshot.boresight_elevation_deg = (
                    snapshot.boresight_elevation_deg
                    or _get_attr_float(alignment, "boresight_elevation_deg")
                )
                snapshot.desired_azimuth_deg = _get_attr_float(
                    alignment, "desired_boresight_azimuth_deg"
                )
                snapshot.desired_elevation_deg = _get_attr_float(
                    alignment, "desired_boresight_elevation_deg"
                )

            snapshot.azimuth_delta_deg = compute_azimuth_delta(
                snapshot.boresight_azimuth_deg, snapshot.desired_azimuth_deg
            )

        except (GrpcError, Exception) as exc:
            snapshot.dish_reachable = False
            snapshot.error_message = str(exc)

        return snapshot


def _get_attr_float(obj, attr: str) -> Optional[float]:
    if obj is None:
        return None
    return _float_or_none(getattr(obj, attr, None))


def _float_or_none(val) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _str_or_none(val) -> Optional[str]:
    if val is None:
        return None
    text = str(val).strip()
    return text if text else None


def _get_attr_bool(obj, attr: str) -> Optional[bool]:
    if obj is None:
        return None
    val = getattr(obj, attr, None)
    if val is None:
        return None
    return bool(val)
