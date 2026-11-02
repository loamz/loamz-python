"""The calls this client makes, as (method, path under /api/v1/workspaces/{workspace}). A test holds this table to the vendored OpenAPI
of the Data server (contracts/data/v1), so the client cannot call something the server does not offer."""

from __future__ import annotations

OPERATIONS: tuple[tuple[str, str], ...] = (
    ("POST", "/sql/statements"),
    ("GET", "/runs/{id}"),
    ("GET", "/securables"),
    ("GET", "/tables/{id}"),
)
