"""Background polling worker for gRPC and network checks."""

from __future__ import annotations

from dataclasses import fields

from PyQt6.QtCore import QThread, pyqtSignal

from starlink_widget.core.config import AppConfig
from starlink_widget.core.connectivity import check_internet
from starlink_widget.core.models import StatusSnapshot
from starlink_widget.core.network_detect import (
    StarlinkPresenceTracker,
    can_reach_dish,
    clear_isp_cache,
    get_off_network_label,
)
from starlink_widget.core.starlink_client import StarlinkClient
from starlink_widget.core.state import (
    PingDropObstructionTracker,
    apply_ping_drop_obstruction,
    collect_critical_alerts,
    resolve_internet_ok,
)


class PollWorker(QThread):
    snapshot_ready = pyqtSignal(object)  # StatusSnapshot
    visibility_changed = pyqtSignal(bool)

    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self._client = StarlinkClient(config)
        self._presence_tracker = StarlinkPresenceTracker(
            hide_after_ticks=config.hide_after_ticks_off_network,
            reboot_grace_ticks=config.dish_reboot_grace_ticks,
        )
        self._ping_obstruct_tracker = PingDropObstructionTracker()
        self._running = True
        self._last_visible: bool | None = None

    def stop(self) -> None:
        self._running = False
        self._client.close()

    def run(self) -> None:
        while self._running:
            protocol_ok = can_reach_dish(
                self.config.starlink_host,
                self.config.starlink_port,
            )
            on_lan, visible = self._presence_tracker.update(protocol_ok)
            if visible != self._last_visible:
                if visible:
                    clear_isp_cache()
                self._last_visible = visible
                self.visibility_changed.emit(visible)

            snapshot = StatusSnapshot(on_starlink_lan=on_lan)

            if on_lan:
                dish = self._client.fetch_status()
                skip = {
                    "on_starlink_lan",
                    "internet_ok",
                    "critical_alerts",
                    "off_network_label",
                }
                for f in fields(StatusSnapshot):
                    if f.name in skip:
                        continue
                    setattr(snapshot, f.name, getattr(dish, f.name))

                if dish.dish_reachable:
                    ping_ok = check_internet(self.config.ping_target)
                    snapshot.internet_ok = resolve_internet_ok(snapshot, ping_ok)
                else:
                    snapshot.internet_ok = False

                apply_ping_drop_obstruction(snapshot, self._ping_obstruct_tracker)
                snapshot.critical_alerts = collect_critical_alerts(snapshot)
            else:
                snapshot.off_network_label = get_off_network_label(
                    daily_max=self.config.isp_lookup_daily_max
                )

            self.snapshot_ready.emit(snapshot)
            self.msleep(self.config.poll_interval_ms)
