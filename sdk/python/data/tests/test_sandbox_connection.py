"""Inside a sandbox the client uses the mounted socket and holds no credential."""

import socket
import tempfile
from pathlib import Path

import loamz.data as ld


def test_in_a_sandbox_the_client_has_a_socket_and_no_credential(monkeypatch):
    directory = Path(tempfile.mkdtemp(prefix="sb-"))  # a Unix socket path must stay short
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(directory / "api.sock"))
    monkeypatch.setattr(ld, "SANDBOX_DIR", directory)
    monkeypatch.setenv("LOAMZ_TOKEN", "must-not-be-used")
    try:
        client = ld.connect()
        assert client.credential is None
        assert (directory / "token").exists() is False
    finally:
        listener.close()
