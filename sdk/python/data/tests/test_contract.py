"""The client is held to the Data server's published API (contracts/data/v1, vendored from loamz-data): every call it makes is in the spec,
the vendored copy is the one its hash names, and the client makes no call the OPERATIONS table does not list."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from loamz.data import client
from loamz.data.operations import OPERATIONS

CONTRACT = Path(__file__).resolve().parents[4] / "contracts" / "data" / "v1"
PREFIX = "/api/v1/workspaces/{ws}"


def test_the_vendored_spec_is_the_one_its_hash_names() -> None:
    wanted = (CONTRACT / "SHA256").read_text().strip()
    assert hashlib.sha256((CONTRACT / "openapi.yaml").read_bytes()).hexdigest() == wanted


def test_every_operation_the_client_uses_is_in_the_servers_spec() -> None:
    paths = yaml.safe_load((CONTRACT / "openapi.yaml").read_text())["paths"]
    for method, path in OPERATIONS:
        entry = paths.get(PREFIX + path.replace("{id}", "{id}"))
        assert entry is not None, f"{path} is not in the spec"
        assert method.lower() in entry, f"{method} {path} is not in the spec"


def test_the_client_makes_no_call_outside_the_table() -> None:
    source = Path(client.__file__).read_text()
    found = {
        (method, re.sub(r"\{[^}]*\}", "{id}", path).replace("{id}{suffix}", "").replace("/securables{id}", "/securables"))
        for method, path in re.findall(r'call\(\s*"(\w+)",\s*f?"([^"]+)"', source)
    }
    normal = {(m, "/securables" if p.startswith("/securables") else p) for m, p in found}
    assert normal <= set(OPERATIONS), normal - set(OPERATIONS)
