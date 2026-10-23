"""`client.legal_holds` and `client.access_tokens`: keep data a legal matter needs, and credentials for scripts.

hold = client.legal_holds.place("tenant", "Litigation 42", tenant_id=tenant, case_ref="CASE-42")
client.erasure.request("gina", tenant_id=tenant)         # raises LegalHoldError (423) while the hold is active
client.legal_holds.release(hold["id"])

created = client.access_tokens.create("ci", expires_in_days=30)
DataClient(endpoint, created["token"])                    # the token is shown once
for token in client.access_tokens.list(): print(token["name"], token["expires_at"])
client.access_tokens.rotate(created["id"]); client.access_tokens.revoke(created["id"])
"""

from __future__ import annotations

from typing import Any

from loamz.core.paging import AsyncItemPaged, ItemPaged
from loamz.core.transport import AsyncTransport, SyncTransport


def _body(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _hold_body(scope, reason, tenant_id, subject, table_id, case_ref) -> dict[str, Any]:
    return _body(
        scope=scope,
        reason=reason,
        tenant_id=tenant_id,
        subject=subject,
        table_id=table_id,
        case_ref=case_ref,
    )


def _token(page: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    return page["items"], page.get("next_page_token")


class LegalHolds:
    def __init__(self, core: SyncTransport):
        self._core = core

    def place(
        self,
        scope: str,
        reason: str,
        *,
        tenant_id: str | None = None,
        subject: str | None = None,
        table_id: str | None = None,
        case_ref: str | None = None,
    ) -> dict[str, Any]:
        """Hold a `tenant`, one `user` (`subject`) of a tenant, or one `table` (`table_id`)."""
        body = _hold_body(scope, reason, tenant_id, subject, table_id, case_ref)
        return self._core.call("POST", "/legal-holds", json=body)

    def list(
        self, *, tenant_id: str | None = None, active: bool = True, page_size: int = 50
    ) -> ItemPaged[dict[str, Any]]:
        def page(token: str | None):
            params = _body(
                tenant_id=tenant_id, active=active, page_size=page_size, page_token=token
            )
            return _token(self._core.call("GET", "/legal-holds", params=params))

        return ItemPaged(page)

    def release(self, hold_id: str) -> dict[str, Any]:
        return self._core.call("POST", f"/legal-holds/{hold_id}:release")


class AsyncLegalHolds:
    def __init__(self, core: AsyncTransport):
        self._core = core

    async def place(
        self,
        scope: str,
        reason: str,
        *,
        tenant_id: str | None = None,
        subject: str | None = None,
        table_id: str | None = None,
        case_ref: str | None = None,
    ) -> dict[str, Any]:
        body = _hold_body(scope, reason, tenant_id, subject, table_id, case_ref)
        return await self._core.call("POST", "/legal-holds", json=body)

    def list(
        self, *, tenant_id: str | None = None, active: bool = True, page_size: int = 50
    ) -> AsyncItemPaged[dict[str, Any]]:
        async def page(token: str | None):
            params = _body(
                tenant_id=tenant_id, active=active, page_size=page_size, page_token=token
            )
            return _token(await self._core.call("GET", "/legal-holds", params=params))

        return AsyncItemPaged(page)

    async def release(self, hold_id: str) -> dict[str, Any]:
        return await self._core.call("POST", f"/legal-holds/{hold_id}:release")


class AccessTokens:
    def __init__(self, core: SyncTransport):
        self._core = core

    def create(
        self, name: str, *, expires_in_days: int | None = None, read_only: bool = False
    ) -> dict[str, Any]:
        """A new personal access token. The secret (`token`) is returned once; sign in as yourself to call this."""
        body = _body(name=name, expires_in_days=expires_in_days, read_only=read_only or None)
        return self._core.call("POST", "/access-tokens", json=body)

    def list(
        self, *, all: bool = False, active: bool = True, page_size: int = 50
    ) -> ItemPaged[dict[str, Any]]:
        def page(token: str | None):
            params = _body(all=all or None, active=active, page_size=page_size, page_token=token)
            return _token(self._core.call("GET", "/access-tokens", params=params))

        return ItemPaged(page)

    def rotate(self, token_id: str) -> dict[str, Any]:
        """A fresh token with the same settings; the old one stops working at once."""
        return self._core.call("POST", f"/access-tokens/{token_id}:rotate")

    def revoke(self, token_id: str) -> None:
        self._core.call("DELETE", f"/access-tokens/{token_id}")


class AsyncAccessTokens:
    def __init__(self, core: AsyncTransport):
        self._core = core

    async def create(
        self, name: str, *, expires_in_days: int | None = None, read_only: bool = False
    ) -> dict[str, Any]:
        body = _body(name=name, expires_in_days=expires_in_days, read_only=read_only or None)
        return await self._core.call("POST", "/access-tokens", json=body)

    def list(
        self, *, all: bool = False, active: bool = True, page_size: int = 50
    ) -> AsyncItemPaged[dict[str, Any]]:
        async def page(token: str | None):
            params = _body(all=all or None, active=active, page_size=page_size, page_token=token)
            return _token(await self._core.call("GET", "/access-tokens", params=params))

        return AsyncItemPaged(page)

    async def rotate(self, token_id: str) -> dict[str, Any]:
        return await self._core.call("POST", f"/access-tokens/{token_id}:rotate")

    async def revoke(self, token_id: str) -> None:
        await self._core.call("DELETE", f"/access-tokens/{token_id}")
