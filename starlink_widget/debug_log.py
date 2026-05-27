"""Instrumentation debug session (NDJSON)."""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path

_LOG_PATH = Path(__file__).resolve().parent.parent / "debug-26b621.log"
_SESSION = "26b621"


def debug_log(
    location: str,
    message: str,
    data: dict | None = None,
    *,
    hypothesis_id: str = "",
    run_id: str = "pre-fix",
) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": _SESSION,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


def debug_exception(
    location: str,
    exc: BaseException,
    *,
    hypothesis_id: str = "",
    run_id: str = "pre-fix",
    extra: dict | None = None,
) -> None:
    debug_log(
        location,
        f"EXCEPTION: {type(exc).__name__}: {exc}",
        {
            "traceback": traceback.format_exc(),
            **(extra or {}),
        },
        hypothesis_id=hypothesis_id,
        run_id=run_id,
    )
