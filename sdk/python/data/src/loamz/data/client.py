"""`DataClient` (sync) and `AsyncDataClient` (asyncio) for a Loamz Data workspace.

    from loamz.data import DataClient
    from loamz.identity import ClientSecretCredential

    client = DataClient(endpoint, ClientSecretCredential(issuer, id, secret), workspace=workspace_id)
    client.tables()                                   # ["shop.main.sales4", ...]: what you may read
    client.rows("SELECT region, sum(amount) FROM shop.main.sales4 GROUP BY 1")
    client.sql("SELECT ...")                          # a Polars DataFrame (the [arrow] extra)

Everything is scoped to one workspace. Statements run on the workspace's compute under the signed-in person's rights: a table
you may not read is simply not there. Idempotent requests are retried on 429/502/503/504 (honouring `Retry-After`), every
request carries a W3C `traceparent`, and errors are `HttpResponseError` subclasses.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Self

import httpx

from loamz.core.credentials import TokenSource
from loamz.core.exceptions import HttpResponseError, InvalidRequestError, NotFoundError
from loamz.core.transport import AsyncTransport, RetryPolicy, SyncTransport
from loamz.data.models import Column, Json, JsonObject, QueryResult, TableInfo

API_VERSION = "v1"
DEFAULT_ENDPOINT = "http://127.0.0.1:8020"
_RUNNING = frozenset({"queued", "running"})
_POLL_S = 0.7


def _object(value: Json) -> JsonObject:
    if not isinstance(value, dict):
        raise HttpResponseError(
            502, {"detail": "the server answered with something that is not an object"}
        )
    return value


def _items(value: Json) -> list[JsonObject]:
    body = _object(value).get("items", [])
    return [item for item in body if isinstance(item, dict)] if isinstance(body, list) else []


def _text(obj: JsonObject, key: str) -> str:
    value = obj.get(key, "")
    return value if isinstance(value, str) else ""


def result_of(run: JsonObject) -> QueryResult:
    """The rows of a finished run, or the reason it did not finish."""
    state = _text(run, "state")
    if state != "succeeded":
        reason = _text(run, "error") or f"the statement {state.replace('_', ' ')}"
        raise InvalidRequestError(400, {"detail": reason})
    body = run.get("result")
    if not isinstance(body, dict):
        raise HttpResponseError(502, {"detail": "a finished statement came back without a result"})
    columns = tuple(
        Column(_text(c, "name"), _text(c, "type"))
        for c in (body.get("columns") or [])
        if isinstance(c, dict)
    )
    raw_rows = body.get("rows")
    rows = (
        tuple(tuple(r) for r in raw_rows if isinstance(r, list))
        if isinstance(raw_rows, list)
        else ()
    )
    return QueryResult(columns, rows, bool(body.get("truncated")), _text(run, "id"))


def table_info(entry: JsonObject, full_name: str, described: JsonObject) -> TableInfo:
    raw = described.get("columns")
    columns = tuple(
        Column(_text(c, "name"), str(c.get("type", "")))
        for c in (raw if isinstance(raw, list) else [])
        if isinstance(c, dict)
    )
    props = described.get("properties")
    properties = {str(k): str(v) for k, v in props.items()} if isinstance(props, dict) else {}
    return TableInfo(
        _text(entry, "id"), full_name, columns, _text(described, "current_snapshot"), properties
    )


class DataClient:
    """Synchronous client. Thread-safe; share one per process."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        credential: TokenSource = None,
        *,
        workspace: str,
        timeout: float = 600,
        transport: httpx.BaseTransport | None = None,
        retry: RetryPolicy | None = RetryPolicy(),
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not workspace:
            raise ValueError("a workspace id is needed: every call is scoped to one workspace")
        self.credential = credential
        self.workspace = workspace
        self._sleep = sleep
        self._core = SyncTransport(
            base_url=endpoint.rstrip("/") + f"/api/{API_VERSION}/workspaces/{workspace}",
            credential=credential,
            timeout=timeout,
            transport=transport,
            retry=retry,
            sleep=sleep,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def close(self) -> None:
        self._core.close()

    # ------------------------------------------------------------------ SQL
    def run(self, query: str, *, limit: int = 1000, wait_s: int = 30) -> JsonObject:
        """Submit a read-only statement and follow it to its end; the finished run, as the server describes it."""
        run = _object(
            self._core.call(
                "POST", "/sql/statements", json={"sql": query, "limit": limit, "wait_s": wait_s}
            )
        )
        while _text(run, "state") in _RUNNING:
            self._sleep(_POLL_S)
            run = _object(self._core.call("GET", f"/runs/{_text(run, 'id')}"))
        return run

    def rows(self, query: str, *, limit: int = 1000) -> QueryResult:
        """A statement's rows as plain values; works without the Arrow extra."""
        return result_of(self.run(query, limit=limit))

    def sql(self, query: str, *, limit: int = 1000):  # type: ignore[no-untyped-def]  # a polars.DataFrame, imported lazily
        """A statement's rows as a Polars DataFrame (the `[arrow]` extra)."""
        from loamz.data import _arrow

        result = self.rows(query, limit=limit)
        return _arrow.polars().DataFrame(
            [list(r) for r in result.rows],
            schema=[c.name for c in result.columns],
            orient="row",
        )

    # ------------------------------------------------------------------ catalog
    def _children(self, parent: str) -> list[JsonObject]:
        suffix = f"?parent_id={parent}" if parent else ""
        return _items(self._core.call("GET", f"/securables{suffix}"))

    def tables(self) -> list[str]:
        """The `catalog.schema.table` names you may read here."""
        names: list[str] = []
        for catalog in self._children(""):
            for schema in self._children(_text(catalog, "id")):
                if _text(schema, "kind") != "schema":
                    continue
                for entry in self._children(_text(schema, "id")):
                    if _text(entry, "kind") == "table":
                        names.append(
                            f"{_text(catalog, 'name')}.{_text(schema, 'name')}.{_text(entry, 'name')}"
                        )
        return sorted(names)

    def describe(self, full_name: str) -> TableInfo:
        """The columns and snapshots of `catalog.schema.table`; not found when you may not read it."""
        parts = full_name.split(".")
        if len(parts) != 3:
            raise InvalidRequestError(400, {"detail": "name a table as catalog.schema.table"})
        parent = ""
        entry: JsonObject = {}
        for part in parts:
            match = [c for c in self._children(parent) if _text(c, "name") == part]
            if not match:
                raise NotFoundError(
                    404, {"detail": f"{full_name} was not found, or you may not read it"}
                )
            entry = match[0]
            parent = _text(entry, "id")
        return table_info(entry, full_name, _object(self._core.call("GET", f"/tables/{parent}")))


class AsyncDataClient:
    """Asyncio client. Safe to share across tasks."""

    def __init__(
        self,
        endpoint: str = DEFAULT_ENDPOINT,
        credential: TokenSource = None,
        *,
        workspace: str,
        timeout: float = 600,
        transport: httpx.AsyncBaseTransport | None = None,
        retry: RetryPolicy | None = RetryPolicy(),
    ) -> None:
        if not workspace:
            raise ValueError("a workspace id is needed: every call is scoped to one workspace")
        self.credential = credential
        self.workspace = workspace
        self._core = AsyncTransport(
            base_url=endpoint.rstrip("/") + f"/api/{API_VERSION}/workspaces/{workspace}",
            credential=credential,
            timeout=timeout,
            transport=transport,
            retry=retry,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._core.close()

    async def run(self, query: str, *, limit: int = 1000, wait_s: int = 30) -> JsonObject:
        run = _object(
            await self._core.call(
                "POST", "/sql/statements", json={"sql": query, "limit": limit, "wait_s": wait_s}
            )
        )
        while _text(run, "state") in _RUNNING:
            await asyncio.sleep(_POLL_S)
            run = _object(await self._core.call("GET", f"/runs/{_text(run, 'id')}"))
        return run

    async def rows(self, query: str, *, limit: int = 1000) -> QueryResult:
        return result_of(await self.run(query, limit=limit))

    async def _children(self, parent: str) -> list[JsonObject]:
        suffix = f"?parent_id={parent}" if parent else ""
        return _items(await self._core.call("GET", f"/securables{suffix}"))

    async def tables(self) -> list[str]:
        names: list[str] = []
        for catalog in await self._children(""):
            for schema in await self._children(_text(catalog, "id")):
                if _text(schema, "kind") != "schema":
                    continue
                for entry in await self._children(_text(schema, "id")):
                    if _text(entry, "kind") == "table":
                        names.append(
                            f"{_text(catalog, 'name')}.{_text(schema, 'name')}.{_text(entry, 'name')}"
                        )
        return sorted(names)

    async def describe(self, full_name: str) -> TableInfo:
        parts = full_name.split(".")
        if len(parts) != 3:
            raise InvalidRequestError(400, {"detail": "name a table as catalog.schema.table"})
        parent = ""
        entry: JsonObject = {}
        for part in parts:
            match = [c for c in await self._children(parent) if _text(c, "name") == part]
            if not match:
                raise NotFoundError(
                    404, {"detail": f"{full_name} was not found, or you may not read it"}
                )
            entry = match[0]
            parent = _text(entry, "id")
        return table_info(
            entry, full_name, _object(await self._core.call("GET", f"/tables/{parent}"))
        )


__all__ = ["API_VERSION", "AsyncDataClient", "DataClient", "result_of"]
