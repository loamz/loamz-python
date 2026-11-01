"""The workspace client against a stand-in server: statements (finished and polled), the catalog, and what a refusal looks like."""

from __future__ import annotations

import json

import httpx
import pytest

from loamz.core.exceptions import InvalidRequestError
from loamz.data import AsyncDataClient, DataClient

WS = "9cce7e59-e1c0-4f8b-ab20-ff93a79161ca"
BASE = f"/api/v1/workspaces/{WS}"
RESULT = {
    "columns": [{"name": "region", "type": "VARCHAR"}, {"name": "n", "type": "BIGINT"}],
    "rows": [["north", 2], ["south", 1]],
    "truncated": False,
}


class Server:
    """Answers like Loamz Data and records what it was asked."""

    def __init__(self, *, polls: int = 0, state: str = "succeeded", error: str = "") -> None:
        self.seen: list[tuple[str, str, dict[str, object]]] = []
        self.polls, self.final, self.error = polls, state, error

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        path = request.url.path + (f"?{request.url.query.decode()}" if request.url.query else "")
        self.seen.append((request.method, path, body))
        if path == f"{BASE}/sql/statements":
            if self.polls:
                return httpx.Response(202, json={"id": "r1", "state": "queued"})
            return httpx.Response(200, json=self._run())
        if path == f"{BASE}/runs/r1":
            self.polls -= 1
            return httpx.Response(
                200, json=self._run() if self.polls <= 0 else {"id": "r1", "state": "running"}
            )
        children = {
            f"{BASE}/securables": [
                {"id": "c1", "kind": "catalog", "name": "shop", "parent_id": ""}
            ],
            f"{BASE}/securables?parent_id=c1": [
                {"id": "s1", "kind": "schema", "name": "main", "parent_id": "c1"}
            ],
            f"{BASE}/securables?parent_id=s1": [
                {"id": "t1", "kind": "table", "name": "sales", "parent_id": "s1"},
                {"id": "v1", "kind": "volume", "name": "files", "parent_id": "s1"},
            ],
        }
        if path in children:
            return httpx.Response(200, json={"items": children[path]})
        if path == f"{BASE}/tables/t1":
            return httpx.Response(
                200,
                json={
                    "columns": [{"id": 1, "name": "region", "type": "string", "required": False}],
                    "current_snapshot": "42",
                    "properties": {},
                },
            )
        return httpx.Response(404, json={"title": "Not Found", "detail": "not found"})

    def _run(self) -> dict[str, object]:
        run: dict[str, object] = {"id": "r1", "state": self.final, "error": self.error}
        if self.final == "succeeded":
            run["result"] = RESULT
        return run


def client(server: Server) -> DataClient:
    return DataClient(
        "http://data.test",
        workspace=WS,
        transport=httpx.MockTransport(server),
        sleep=lambda _: None,
    )


def test_a_workspace_is_required() -> None:
    with pytest.raises(ValueError, match="workspace"):
        DataClient("http://data.test", workspace="")


def test_a_finished_statement_comes_back_as_typed_rows() -> None:
    server = Server()
    result = client(server).rows("SELECT region, n FROM shop.main.sales", limit=50)
    assert [c.name for c in result.columns] == ["region", "n"]
    assert result.to_dicts() == [{"region": "north", "n": 2}, {"region": "south", "n": 1}]
    assert server.seen[0][2]["limit"] == 50 and server.seen[0][2]["sql"].startswith("SELECT")  # type: ignore[union-attr]


def test_a_statement_still_running_is_followed_until_it_ends() -> None:
    server = Server(polls=3)
    assert len(client(server).rows("SELECT 1").rows) == 2
    assert [m for m, p, _ in server.seen if p == f"{BASE}/runs/r1"] == ["GET"] * 3


def test_a_statement_that_failed_says_why() -> None:
    with pytest.raises(InvalidRequestError, match="Binder Error"):
        client(Server(state="failed", error="Binder Error: no column nope")).rows("SELECT nope")


def test_tables_lists_only_tables_in_full_and_describe_shows_columns() -> None:
    c = client(Server())
    assert c.tables() == ["shop.main.sales"]
    info = c.describe("shop.main.sales")
    assert (info.id, info.current_snapshot, [col.name for col in info.columns]) == (
        "t1",
        "42",
        ["region"],
    )
    with pytest.raises(Exception, match="not found"):
        c.describe("shop.main.missing")
    with pytest.raises(InvalidRequestError):
        c.describe("sales")


async def test_the_async_client_does_the_same() -> None:
    server = Server(polls=2)
    async with AsyncDataClient(
        "http://data.test", workspace=WS, transport=httpx.MockTransport(server)
    ) as c:
        assert (await c.rows("SELECT 1")).rows[0] == ("north", 2)
        assert await c.tables() == ["shop.main.sales"]
        assert (await c.describe("shop.main.sales")).id == "t1"


def test_the_arrow_extra_gives_a_dataframe() -> None:
    pytest.importorskip("polars")
    df = client(Server()).sql("SELECT 1")
    assert df.shape == (2, 2) and df.columns == ["region", "n"]
