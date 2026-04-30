from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class AuditLogger:
    """Append-only JSONL audit logger.

    Every important decision should be recorded here so the system can explain
    why it watched, rejected, or approved a paper trade idea.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, event_type: str, payload: BaseModel | dict[str, Any]) -> None:
        if isinstance(payload, BaseModel):
            data = payload.model_dump(mode="json")
        else:
            data = payload

        event = {
            "event_type": event_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "payload": data,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
