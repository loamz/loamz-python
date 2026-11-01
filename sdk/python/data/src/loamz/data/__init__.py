"""Client for Loamz Data: governed SQL and the catalog of one workspace (sync and async).

    from loamz.data import DataClient
    from loamz.identity import DefaultLoamzCredential

    client = DataClient("https://data.example.com", DefaultLoamzCredential(), workspace=workspace_id)
    df = client.sql("SELECT region, count(*) AS n FROM shop.main.sales GROUP BY 1")

    from loamz.data.aio import DataClient          # the same client for asyncio

Module-level helpers connect lazily and discover their connection, so agent code is one line:

    import loamz.data as sd
    df = sd.sql("SELECT ...")

Inside a Loamz code-interpreter sandbox the connection is a Unix socket mounted at `/run/loamz-data` and the workspace is in
`LOAMZ_DATA_WORKSPACE`. The sandbox holds no credential: the host's gateway behind the socket speaks for the run's person, so
there is nothing for agent code to print. Elsewhere set `LOAMZ_ENDPOINT`, `LOAMZ_DATA_WORKSPACE` and a credential
(`LOAMZ_TOKEN`, or `LOAMZ_CLIENT_ID`, `LOAMZ_CLIENT_SECRET` and `LOAMZ_ISSUER`; see `loamz.identity`).

The core depends only on httpx. `sd.sql` needs the Arrow extra (`pip install 'loamz-data[arrow]'`); `sd.rows` returns plain values
without it.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import httpx

from loamz.core.credentials import TokenSource
from loamz.data.client import AsyncDataClient, DataClient
from loamz.data.models import Column, QueryResult, TableInfo
from loamz.identity import DefaultLoamzCredential, default_endpoint

SANDBOX_DIR = Path("/run/loamz-data")
SANDBOX_HOST = "http://loamz-data"
WORKSPACE_ENV = "LOAMZ_DATA_WORKSPACE"
_lock = threading.Lock()
_default: DataClient | None = None


def _sandbox() -> Path | None:
    socket = SANDBOX_DIR / "api.sock"
    return socket if socket.exists() else None


def _workspace(workspace: str | None) -> str:
    found = workspace or os.environ.get(WORKSPACE_ENV, "")
    if not found:
        raise RuntimeError(f"No workspace: pass one, or set {WORKSPACE_ENV}.")
    return found


def _from_environment(endpoint: str | None, credential: TokenSource) -> tuple[str, TokenSource]:
    endpoint = endpoint or default_endpoint()
    if not endpoint:
        raise RuntimeError(
            "No Loamz Data connection: not in a sandbox, and LOAMZ_ENDPOINT (or a ~/.loamz/config profile) is not set."
        )
    return endpoint, credential or DefaultLoamzCredential()


def connect(
    endpoint: str | None = None, credential: TokenSource = None, *, workspace: str | None = None
) -> DataClient:
    """A client for this environment: the sandbox socket if present, else the endpoint and credential given or found."""
    sandbox = _sandbox() if endpoint is None else None
    if sandbox:
        # No credential: the gateway on the far end of the socket adds the run's identity itself.
        return DataClient(
            SANDBOX_HOST,
            workspace=_workspace(workspace),
            transport=httpx.HTTPTransport(uds=str(sandbox)),
        )
    found_endpoint, found = _from_environment(endpoint, credential)
    return DataClient(found_endpoint, found, workspace=_workspace(workspace))


def aconnect(
    endpoint: str | None = None, credential: TokenSource = None, *, workspace: str | None = None
) -> AsyncDataClient:
    """`connect()` for asyncio code (same discovery)."""
    sandbox = _sandbox() if endpoint is None else None
    if sandbox:
        return AsyncDataClient(
            SANDBOX_HOST,
            workspace=_workspace(workspace),
            transport=httpx.AsyncHTTPTransport(uds=str(sandbox)),
        )
    found_endpoint, found = _from_environment(endpoint, credential)
    return AsyncDataClient(found_endpoint, found, workspace=_workspace(workspace))


def _client() -> DataClient:
    global _default
    with _lock:
        if _default is None:
            _default = connect()
        return _default


def sql(query: str, *, limit: int = 1000):  # type: ignore[no-untyped-def]  # a polars.DataFrame, imported lazily
    """Run a read-only SELECT and get a Polars DataFrame. Filters and aggregation run on the workspace's compute."""
    return _client().sql(query, limit=limit)


def rows(query: str, *, limit: int = 1000) -> QueryResult:
    """The same as plain values; works without the Arrow extra."""
    return _client().rows(query, limit=limit)


def tables() -> list[str]:
    """The `catalog.schema.table` names you may read."""
    return _client().tables()


def describe(full_name: str) -> TableInfo:
    """The columns and snapshots of `catalog.schema.table`."""
    return _client().describe(full_name)


__all__ = [
    "AsyncDataClient",
    "Column",
    "DataClient",
    "QueryResult",
    "TableInfo",
    "aconnect",
    "connect",
    "describe",
    "rows",
    "sql",
    "tables",
]
