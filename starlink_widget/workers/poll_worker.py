"""Background polling worker for gRPC and network checks."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from starlink_widget.core.config import AppConfig
from starlink_widget.core.connectivity import check_internet
from starlink_widget.core.models import StatusSnapshot
from starlink_widget.core.network_detect import (
    NetworkPresenceTracker,
    is_on_starlink_lan,
)
from starlink_widget.core.starlink_client import StarlinkClient
from starlink_widget.core.state import collect_critical_alerts


class PollWorker(QThread):
    snapshot_ready = pyqtSignal(object)  # StatusSnapshot
    visibility_changed = pyqtSignal(bool)

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self._client = StarlinkClient(config)
        self._network_tracker = NetworkPresenceTracker(
            hide_after_ticks=config.hide_after_ticks_off_network
        )
        self._running = True
        self._last_visible = True

    def stop(self) -> None:
        self._running = False
        self._client.close()

    def run(self) -> None:
        while self._running:
            on_lan = is_on_starlink_lan(self.config)
            visible = self._network_tracker.update(on_lan)
            if visible != self._last_visible:
                self._last_visible = visible
                self.visibility_changed.emit(visible)

            snapshot = StatusSnapshot(on_starlink_lan=visible)

            if visible:
                dish = self._client.fetch_status()
                snapshot.dish_reachable = dish.dish_reachable
                snapshot.state = dish.state
                snapshot.software_version = dish.software_version
                snapshot.downlink_mbps = dish.downlink_mbps
                snapshot.uplink_mbps = dish.uplink_mbps
                snapshot.currently_obstructed = dish.currently_obstructed
                snapshot.fraction_obstructed = dish.fraction_obstructed
                snapshot.alert_obstructed = dish.alert_obstructed
                snapshot.alert_slow_ethernet = dish.alert_slow_ethernet
                snapshot.alert_thermal_shutdown = dish.alert_thermal_shutdown
                snapshot.alert_motors_stuck = dish.alert_motors_stuck
                snapshot.alert_heating = dish.alert_heating
                snapshot.alert_power_thermal_throttle = (
                    dish.alert_power_thermal_throttle
                )
                snapshot.boresight_azimuth_deg = dish.boresight_azimuth_deg
                snapshot.boresight_elevation_deg = dish.boresight_elevation_deg
                snapshot.desired_azimuth_deg = dish.desired_azimuth_deg
                snapshot.desired_elevation_deg = dish.desired_elevation_deg
                snapshot.azimuth_delta_deg = dish.azimuth_delta_deg
                snapshot.error_message = dish.error_message

                if dish.dish_reachable:
                    snapshot.internet_ok = check_internet(self.config.ping_target)
                else:
                    snapshot.internet_ok = False

                snapshot.critical_alerts = collect_critical_alerts(snapshot)
            else:
                snapshot.on_starlink_lan = False

            self.snapshot_ready.emit(snapshot)
            self.msleep(self.config.poll_interval_ms)
