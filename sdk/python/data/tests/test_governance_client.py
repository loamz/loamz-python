"""Legal holds and access tokens through the client (paths, bodies, pagers), and the typed legal-hold error."""

import json

import httpx

from loamz.core.exceptions import LegalHoldError, error_for
from loamz.data import DataClient


def client(handler):
    return DataClient("http://data.test", "tok", transport=httpx.MockTransport(handler), retry=None)


def test_a_hold_is_placed_listed_across_pages_and_released():
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "POST" and request.url.path.endswith("/legal-holds"):
            return httpx.Response(201, json={"id": "h1", "active": True})
        if request.method == "GET":
            token = request.url.params.get("page_token")
            if token is None:
                return httpx.Response(200, json={"items": [{"id": "h1"}], "next_page_token": "t2"})
            return httpx.Response(200, json={"items": [{"id": "h2"}], "next_page_token": None})
        return httpx.Response(200, json={"id": "h1", "active": False})

    with client(handle) as api:
        placed = api.legal_holds.place(
            "user", "case", tenant_id="acme", subject="gina", case_ref="C-1"
        )
        assert placed["id"] == "h1"
        assert json.loads(seen[0].content) == {
            "scope": "user",
            "reason": "case",
            "tenant_id": "acme",
            "subject": "gina",
            "case_ref": "C-1",
        }
        assert [h["id"] for h in api.legal_holds.list(tenant_id="acme")] == ["h1", "h2"]
        assert api.legal_holds.release("h1")["active"] is False
    assert seen[-1].url.path.endswith("/legal-holds/h1:release")


def test_tokens_are_created_rotated_and_revoked():
    seen = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(201, json={"id": "a1", "token": "lpat_a1.secret", "name": "ci"})

    with client(handle) as api:
        created = api.access_tokens.create("ci", expires_in_days=30, read_only=True)
        assert created["token"].startswith("lpat_")
        api.access_tokens.rotate("a1")
        assert api.access_tokens.revoke("a1") is None
    assert json.loads(seen[0].content) == {"name": "ci", "expires_in_days": 30, "read_only": True}
    assert [r.method + " " + r.url.path.removeprefix("/api/v1") for r in seen] == [
        "POST /access-tokens",
        "POST /access-tokens/a1:rotate",
        "DELETE /access-tokens/a1",
    ]


def test_a_423_problem_is_a_legal_hold_error():
    body = {"type": "https://loamz.com/problems/legal-hold", "detail": "held (CASE-42)"}
    error = error_for(423, body)
    assert (
        isinstance(error, LegalHoldError) and error.status == 423 and "CASE-42" in str(error.detail)
    )
