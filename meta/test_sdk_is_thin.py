"""The SDKs are clients: no server framework, database driver or engine in any of their dependencies (rule R8)."""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {"fastapi", "uvicorn", "starlette", "sqlalchemy", "asyncpg", "psycopg", "alembic", "pyjwt", "loamz-engine", "loamz-runtime"}


def name(requirement: str) -> str:
    for cut in "[<>=!~ ;@":
        requirement = requirement.split(cut)[0]
    return requirement.lower()


def test_no_sdk_depends_on_a_server_library() -> None:
    manifests = sorted((ROOT / "sdk").glob("*/*/pyproject.toml"))
    assert manifests, "found no SDK manifests"
    for manifest in manifests:
        project = tomllib.loads(manifest.read_text())["project"]
        requirements = list(project.get("dependencies", []))
        for extra in project.get("optional-dependencies", {}).values():
            requirements += extra
        bad = {name(r) for r in requirements} & FORBIDDEN
        assert not bad, f"{manifest.relative_to(ROOT)} depends on {sorted(bad)}"
