"""Plain data returned by the agents client."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunEvent:
    """One event of a run's stream: `type` is e.g. `text.delta`, `tool.call`, `run.completed`, `run.failed`."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """The text this event adds to the answer (`text.delta` only)."""
        return (
            (self.data.get("delta") or self.data.get("text") or "")
            if self.type == "text.delta"
            else ""
        )

    @property
    def failed(self) -> bool:
        return self.type in ("run.failed", "error")

    @property
    def finished(self) -> bool:
        return self.type in ("run.completed", "run.failed")


def parse_event(line: str) -> RunEvent | None:
    """A server-sent-events line -> an event; None for keep-alives, comments and `[DONE]`."""
    if not line.startswith("data:"):
        return None
    payload = line[5:].strip()
    if not payload or payload == "[DONE]":
        return None
    data = json.loads(payload)
    return RunEvent(str(data.get("type", "")), data)


def items(body: Any) -> list[Any]:
    """List endpoints answer `{"items": [...]}`; a bare list is accepted too."""
    return body if isinstance(body, list) else (body or {}).get("items", [])
