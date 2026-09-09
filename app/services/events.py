"""Event bus (§88) — in-process dispatch + durable outbox (events table).

Phase 3+ swaps delivery to a queue worker without changing producers (§89).
"""
from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from app.core import database as db

log = logging.getLogger("skillected.events")

EventName = str  # e.g. JOB_PUBLISHED, JOB_EXPIRED, APPLICATION_CLICKED, QR_SCANNED

_handlers: dict[EventName, list[Callable[[dict[str, Any]], None]]] = defaultdict(list)


def on(event: EventName, handler: Callable[[dict[str, Any]], None]) -> None:
    _handlers[event].append(handler)


def emit(event: EventName, entity_type: str = "", entity_id: int | None = None,
         payload: dict[str, Any] | None = None) -> None:
    """Persist to outbox, then dispatch to in-process handlers (errors isolated)."""
    db.execute(
        "INSERT INTO events (event_type, entity_type, entity_id, payload) VALUES (?,?,?,?)",
        (event, entity_type, entity_id,
         json.dumps(payload or {}, default=str)),
    )
    for handler in _handlers.get(event, []):
        try:
            handler(payload or {})
        except Exception:  # noqa: BLE001 — one handler must not break others (§82)
            log.exception("event handler failed for %s", event)
