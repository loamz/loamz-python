"""`AgentsClient(endpoint, credential)`: agents, threads and runs.

client = AgentsClient("https://agents.example.com", DefaultLoamzCredential())
agent = client.create_agent("analyst", instructions="You answer questions about taxi trips.")
thread = client.create_thread(agent_id=agent["id"])
for event in client.invoke_agent(thread["id"], "How many trips were there in June?"):
    print(event.text, end="")
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from loamz.agents.models import RunEvent, items, parse_event
from loamz.core import AsyncItemPaged, ItemPaged
from loamz.core.credentials import TokenSource
from loamz.core.transport import AsyncTransport, RetryPolicy, SyncTransport

API = "/api/v1"


def _body(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _chat(thread_id: str, prompt: str, options: dict[str, Any]) -> dict[str, Any]:
    return _body(thread_id=thread_id, messages=[{"role": "user", "content": prompt}], **options)


class AgentsClient:
    def __init__(
        self,
        endpoint: str,
        credential: TokenSource = None,
        *,
        timeout: float = 600,
        retry: RetryPolicy | None = RetryPolicy(),
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._t = SyncTransport(
            base_url=endpoint.rstrip("/"),
            credential=credential,
            timeout=timeout,
            retry=retry,
            transport=transport,
        )

    def __enter__(self) -> AgentsClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._t.close()

    # ---------------------------------------------------------------- agents
    def list_agents(self) -> ItemPaged[dict[str, Any]]:
        return ItemPaged(lambda _token: (items(self._t.call("GET", f"{API}/agents")), None))

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        return self._t.call("GET", f"{API}/agents/{agent_id}")

    def create_agent(
        self,
        name: str,
        *,
        instructions: str | None = None,
        model: str | None = None,
        role: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        body = _body(
            name=name,
            instructions=instructions,
            model=model,
            role=role,
            allowed_tools=allowed_tools,
        )
        return self._t.call("POST", f"{API}/agents", json=body)

    def update_agent(self, agent_id: str, **changes: Any) -> dict[str, Any]:
        return self._t.call("PATCH", f"{API}/agents/{agent_id}", json=changes)

    def delete_agent(self, agent_id: str) -> None:
        self._t.call("DELETE", f"{API}/agents/{agent_id}")

    def list_tools(self) -> ItemPaged[dict[str, Any]]:
        return ItemPaged(lambda _token: (items(self._t.call("GET", f"{API}/agents/tools")), None))

    # --------------------------------------------------------------- threads
    def list_threads(
        self, *, archived: bool = False, page_size: int = 50
    ) -> ItemPaged[dict[str, Any]]:
        def page(token: str | None) -> tuple[list[dict[str, Any]], str | None]:
            params = _body(archived=archived, page_size=page_size, page_token=token)
            body = self._t.call("GET", f"{API}/threads", params=params)
            return items(body), body.get("next_page_token")

        return ItemPaged(page)

    def create_thread(
        self, *, agent_id: str | None = None, name: str | None = None
    ) -> dict[str, Any]:
        return self._t.call("POST", f"{API}/threads", json=_body(agent_id=agent_id, name=name))

    def get_thread(self, thread_id: str) -> dict[str, Any]:
        return self._t.call("GET", f"{API}/threads/{thread_id}")

    def delete_thread(self, thread_id: str) -> None:
        self._t.call("DELETE", f"{API}/threads/{thread_id}")

    def list_messages(self, thread_id: str) -> ItemPaged[dict[str, Any]]:
        return ItemPaged(
            lambda _token: (items(self._t.call("GET", f"{API}/threads/{thread_id}/messages")), None)
        )

    # ------------------------------------------------------------------ runs
    def invoke_agent(
        self,
        thread_id: str,
        prompt: str,
        *,
        file_ids: list[str] | None = None,
        model: str | None = None,
        system_instructions: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> Iterator[RunEvent]:
        """Send a message and stream the run's events until it finishes."""
        options = _body(
            file_ids=file_ids,
            model=model,
            system_instructions=system_instructions,
            allowed_tools=allowed_tools,
        )
        response = self._t.send(
            "POST", f"{API}/chat", stream=True, json=_chat(thread_id, prompt, options)
        )
        try:
            self._t.check(response)
            for line in response.iter_lines():
                event = parse_event(line)
                if event:
                    yield event
                    if event.finished:
                        return
        finally:
            response.close()

    def cancel_run(self, thread_id: str) -> None:
        self._t.call("POST", f"{API}/chat/{thread_id}/cancel")

    def list_approvals(self) -> ItemPaged[dict[str, Any]]:
        return ItemPaged(lambda _token: (items(self._t.call("GET", f"{API}/approvals")), None))

    def respond_to_approval(self, request_id: str, action: str, **details: Any) -> None:
        self._t.call(
            "POST", f"{API}/chat/respond/{request_id}", json=_body(action=action, **details)
        )


class AsyncAgentsClient:
    def __init__(
        self,
        endpoint: str,
        credential: TokenSource = None,
        *,
        timeout: float = 600,
        retry: RetryPolicy | None = RetryPolicy(),
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._t = AsyncTransport(
            base_url=endpoint.rstrip("/"),
            credential=credential,
            timeout=timeout,
            retry=retry,
            transport=transport,
        )

    async def __aenter__(self) -> AsyncAgentsClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._t.close()

    # ---------------------------------------------------------------- agents
    def list_agents(self) -> AsyncItemPaged[dict[str, Any]]:
        async def page(_token: str | None):
            return items(await self._t.call("GET", f"{API}/agents")), None

        return AsyncItemPaged(page)

    async def get_agent(self, agent_id: str) -> dict[str, Any]:
        return await self._t.call("GET", f"{API}/agents/{agent_id}")

    async def create_agent(
        self,
        name: str,
        *,
        instructions: str | None = None,
        model: str | None = None,
        role: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        body = _body(
            name=name,
            instructions=instructions,
            model=model,
            role=role,
            allowed_tools=allowed_tools,
        )
        return await self._t.call("POST", f"{API}/agents", json=body)

    async def update_agent(self, agent_id: str, **changes: Any) -> dict[str, Any]:
        return await self._t.call("PATCH", f"{API}/agents/{agent_id}", json=changes)

    async def delete_agent(self, agent_id: str) -> None:
        await self._t.call("DELETE", f"{API}/agents/{agent_id}")

    def list_tools(self) -> AsyncItemPaged[dict[str, Any]]:
        async def page(_token: str | None):
            return items(await self._t.call("GET", f"{API}/agents/tools")), None

        return AsyncItemPaged(page)

    # --------------------------------------------------------------- threads
    def list_threads(
        self, *, archived: bool = False, page_size: int = 50
    ) -> AsyncItemPaged[dict[str, Any]]:
        async def page(token: str | None):
            params = _body(archived=archived, page_size=page_size, page_token=token)
            body = await self._t.call("GET", f"{API}/threads", params=params)
            return items(body), body.get("next_page_token")

        return AsyncItemPaged(page)

    async def create_thread(
        self, *, agent_id: str | None = None, name: str | None = None
    ) -> dict[str, Any]:
        return await self._t.call(
            "POST", f"{API}/threads", json=_body(agent_id=agent_id, name=name)
        )

    async def get_thread(self, thread_id: str) -> dict[str, Any]:
        return await self._t.call("GET", f"{API}/threads/{thread_id}")

    async def delete_thread(self, thread_id: str) -> None:
        await self._t.call("DELETE", f"{API}/threads/{thread_id}")

    def list_messages(self, thread_id: str) -> AsyncItemPaged[dict[str, Any]]:
        async def page(_token: str | None):
            return items(await self._t.call("GET", f"{API}/threads/{thread_id}/messages")), None

        return AsyncItemPaged(page)

    # ------------------------------------------------------------------ runs
    async def invoke_agent(
        self,
        thread_id: str,
        prompt: str,
        *,
        file_ids: list[str] | None = None,
        model: str | None = None,
        system_instructions: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> AsyncIterator[RunEvent]:
        options = _body(
            file_ids=file_ids,
            model=model,
            system_instructions=system_instructions,
            allowed_tools=allowed_tools,
        )
        response = await self._t.send(
            "POST", f"{API}/chat", stream=True, json=_chat(thread_id, prompt, options)
        )
        try:
            await self._t.check(response)
            async for line in response.aiter_lines():
                event = parse_event(line)
                if event:
                    yield event
                    if event.finished:
                        return
        finally:
            await response.aclose()

    async def cancel_run(self, thread_id: str) -> None:
        await self._t.call("POST", f"{API}/chat/{thread_id}/cancel")

    def list_approvals(self) -> AsyncItemPaged[dict[str, Any]]:
        async def page(_token: str | None):
            return items(await self._t.call("GET", f"{API}/approvals")), None

        return AsyncItemPaged(page)

    async def respond_to_approval(self, request_id: str, action: str, **details: Any) -> None:
        await self._t.call(
            "POST", f"{API}/chat/respond/{request_id}", json=_body(action=action, **details)
        )
