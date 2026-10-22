"""The agents client against httpx.MockTransport: paths, bodies, pagers and the event stream."""

import asyncio
import json

import httpx

from loamz.agents import AgentsClient, RunEvent
from loamz.agents.aio import AgentsClient as AsyncAgentsClient

SSE = "\n".join(
    [
        'data: {"type": "run.started"}',
        "",
        ": keep-alive",
        'data: {"type": "text.delta", "delta": "Hel"}',
        'data: {"type": "text.delta", "text": "lo"}',
        'data: {"type": "run.completed"}',
        'data: {"type": "text.delta", "delta": "after the end"}',
        "data: [DONE]",
        "",
    ]
)


def handler(seen):
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path == "/api/v1/threads" and request.method == "GET":
            token = request.url.params.get("page_token")
            if token is None:
                return httpx.Response(
                    200, json={"items": [{"id": "t1"}, {"id": "t2"}], "next_page_token": "p2"}
                )
            return httpx.Response(200, json={"items": [{"id": "t3"}], "next_page_token": None})
        if path == "/api/v1/agents" and request.method == "GET":
            return httpx.Response(200, json={"items": [{"id": "a1"}]})
        if path == "/api/v1/agents" and request.method == "POST":
            return httpx.Response(201, json={"id": "a2", **json.loads(request.content)})
        if path == "/api/v1/chat":
            return httpx.Response(200, text=SSE, headers={"content-type": "text/event-stream"})
        if path.startswith("/api/v1/agents/missing"):
            return httpx.Response(
                404,
                json={
                    "type": "https://loamz.com/problems/not-found",
                    "status": 404,
                    "detail": "no",
                },
                headers={"content-type": "application/problem+json"},
            )
        return httpx.Response(204)

    return handle


def client(seen):
    return AgentsClient("http://agents.test", "tok", transport=httpx.MockTransport(handler(seen)))


def test_threads_page_lazily_and_carry_the_bearer():
    seen = []
    with client(seen) as api:
        threads = api.list_threads(page_size=2)
        assert seen == []
        assert [t["id"] for t in threads] == ["t1", "t2", "t3"]
    assert seen[0].headers["authorization"] == "Bearer tok"
    assert seen[1].url.params["page_token"] == "p2" and seen[0].url.params["page_size"] == "2"


def test_create_agent_sends_only_what_was_given():
    seen = []
    with client(seen) as api:
        agent = api.create_agent("analyst", instructions="be brief")
        assert [a["id"] for a in api.list_agents()] == ["a1"]
    assert agent == {"id": "a2", "name": "analyst", "instructions": "be brief"}


def test_an_invoked_run_streams_events_until_it_finishes():
    seen = []
    with client(seen) as api:
        events = list(api.invoke_agent("t1", "hi", file_ids=["f1"]))
    assert [e.type for e in events] == ["run.started", "text.delta", "text.delta", "run.completed"]
    assert "".join(e.text for e in events) == "Hello" and events[-1].finished
    body = json.loads(seen[0].content)
    assert body == {
        "thread_id": "t1",
        "messages": [{"role": "user", "content": "hi"}],
        "file_ids": ["f1"],
    }


def test_errors_are_typed():
    import pytest

    from loamz.core.exceptions import ResourceNotFoundError

    with client([]) as api, pytest.raises(ResourceNotFoundError):
        api.get_agent("missing")


def test_the_async_client_matches_the_sync_one():
    async def run():
        transport = httpx.MockTransport(handler([]))
        async with AsyncAgentsClient("http://agents.test", "tok", transport=transport) as api:
            ids = [t["id"] async for t in api.list_threads()]
            events = [e async for e in api.invoke_agent("t1", "hi")]
        return ids, events

    ids, events = asyncio.run(run())
    assert ids == ["t1", "t2", "t3"] and isinstance(events[0], RunEvent) and events[-1].finished
