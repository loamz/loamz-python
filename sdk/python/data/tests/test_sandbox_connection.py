"""Inside a sandbox the client uses the mounted socket and holds no credential."""

import socket
import tempfile
from pathlib import Path

import pytest

import loamz.data as sd

WS = "9cce7e59-e1c0-4f8b-ab20-ff93a79161ca"


def test_in_a_sandbox_the_client_has_a_socket_and_no_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = Path(tempfile.mkdtemp(prefix="sb-"))  # a Unix socket path must stay short
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(directory / "api.sock"))
    monkeypatch.setattr(sd, "SANDBOX_DIR", directory)
    monkeypatch.setenv("LOAMZ_TOKEN", "must-not-be-used")
    monkeypatch.setenv("LOAMZ_DATA_WORKSPACE", WS)
    try:
        client = sd.connect()
        assert client.credential is None and client.workspace == WS
    finally:
        listener.close()


def test_without_a_workspace_the_helpers_say_what_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LOAMZ_DATA_WORKSPACE", raising=False)
    monkeypatch.setattr(sd, "SANDBOX_DIR", Path("/nonexistent"))
    with pytest.raises(RuntimeError, match="LOAMZ_DATA_WORKSPACE"):
        sd.connect("http://data.test")
