"""What the client returns: plain, typed values. The core needs only httpx."""

from __future__ import annotations

from dataclasses import dataclass, field

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None
type JsonObject = dict[str, Json]


@dataclass(frozen=True, slots=True)
class Column:
    """A column of a result or a table."""

    name: str
    type: str


@dataclass(frozen=True, slots=True)
class QueryResult:
    """The rows of a finished statement. ``truncated`` says the row limit cut it short."""

    columns: tuple[Column, ...]
    rows: tuple[tuple[Json, ...], ...]
    truncated: bool = False
    run_id: str = ""

    def to_dicts(self) -> list[dict[str, Json]]:
        names = [c.name for c in self.columns]
        return [dict(zip(names, row, strict=True)) for row in self.rows]


@dataclass(frozen=True, slots=True)
class TableInfo:
    """A table as the catalog shows it: its name in full, its columns, and where its snapshots stand."""

    id: str
    full_name: str
    columns: tuple[Column, ...]
    current_snapshot: str = ""
    properties: dict[str, str] = field(default_factory=dict)


__all__ = ["Column", "Json", "JsonObject", "QueryResult", "TableInfo"]
