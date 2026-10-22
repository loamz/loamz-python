PYTEST ?= -q -n 4 --timeout=120

.PHONY: sync lint imports test

sync:
	uv sync --all-packages --all-groups

lint:
	uv run ruff check .
	uv run ruff format --check .

imports:
	uv run lint-imports --config .importlinter

test:
	cd sdk/python/core && uv run --package loamz-core pytest $(PYTEST)
	cd sdk/python/identity && uv run --package loamz-identity pytest $(PYTEST)
	cd sdk/python/data && uv run --package loamz-data pytest $(PYTEST)
	cd sdk/python/agents && uv run --package loamz-agents pytest $(PYTEST)
