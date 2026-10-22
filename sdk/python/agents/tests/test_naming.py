"""The client naming standard: verbs are list_/get_/create_/update_/delete_/begin_ or a plain verb phrase, and the
asyncio client has the same methods as the sync one."""

import inspect

from loamz.agents import AgentsClient, AsyncAgentsClient
from loamz.core import AsyncItemPaged, ItemPaged

BANNED_PREFIXES = ("fetch_", "retrieve_", "remove_", "add_", "make_", "all_", "find_")


def public(cls):
    return {n for n, _ in inspect.getmembers(cls, inspect.isroutine) if not n.startswith("_")}


def test_no_off_standard_verbs():
    for name in public(AgentsClient):
        assert not name.startswith(BANNED_PREFIXES), name


def test_the_async_client_mirrors_the_sync_one():
    assert public(AgentsClient) == public(AsyncAgentsClient)


def test_list_methods_return_pagers():
    for name in public(AgentsClient):
        if name.startswith("list_"):
            assert "ItemPaged" in str(
                inspect.signature(getattr(AgentsClient, name)).return_annotation
            ), name
    assert ItemPaged and AsyncItemPaged
