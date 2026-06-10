"""Configuration loading from config.json and environment."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from starlink_widget.core.paths import app_root


@dataclass
class AppConfig:
    starlink_host: str = "192.168.100.1"
    starlink_port: int = 9200
    ping_target: str = "1.1.1.1"
    poll_interval_ms: int = 1000
    starlink_gateway_prefixes: List[str] = field(
        default_factory=lambda: ["192.168.1."]
    )
    starlink_wifi_ssids: List[str] = field(default_factory=list)
    starlink_require_dish_route: bool = True
    hide_after_ticks_off_network: int = 1
    isp_lookup_daily_max: int = 5

    @property
    def starlink_target(self) -> str:
        return f"{self.starlink_host}:{self.starlink_port}"


def load_config(path: Optional[Path] = None) -> AppConfig:
    cfg = AppConfig()
    config_path = path or (app_root() / "config.json")
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        for key, value in data.items():
            attr = key.lower()
            if hasattr(cfg, attr):
                setattr(cfg, attr, value)

    if host := os.environ.get("STARLINK_HOST"):
        cfg.starlink_host = host
    if port := os.environ.get("STARLINK_PORT"):
        cfg.starlink_port = int(port)
    if target := os.environ.get("PING_TARGET"):
        cfg.ping_target = target
    if interval := os.environ.get("POLL_INTERVAL_MS"):
        cfg.poll_interval_ms = int(interval)
    return cfg


def config_path() -> Path:
    return app_root() / "config.json"
