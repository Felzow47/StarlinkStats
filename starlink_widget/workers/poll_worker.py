"""Background polling worker for gRPC and network checks."""

from __future__ import annotations

from dataclasses import fields

from PyQt6.QtCore import QThread, pyqtSignal

from starlink_widget.core.config import AppConfig
from starlink_widget.core.connectivity import check_internet
from starlink_widget.core.models import StatusSnapshot
from starlink_widget.core.network_detect import (
    NetworkPresenceTracker,
    is_on_starlink_lan,
)
from starlink_widget.core.starlink_client import StarlinkClient
from starlink_widget.core.state import collect_critical_alerts, resolve_internet_ok


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
                skip = {"on_starlink_lan", "internet_ok", "critical_alerts"}
                for f in fields(StatusSnapshot):
                    if f.name in skip:
                        continue
                    setattr(snapshot, f.name, getattr(dish, f.name))

                if dish.dish_reachable:
                    ping_ok = check_internet(self.config.ping_target)
                    snapshot.internet_ok = resolve_internet_ok(snapshot, ping_ok)
                else:
                    snapshot.internet_ok = False

                snapshot.critical_alerts = collect_critical_alerts(snapshot)
            else:
                snapshot.on_starlink_lan = False

            self.snapshot_ready.emit(snapshot)
            self.msleep(self.config.poll_interval_ms)
