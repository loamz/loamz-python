# Contributing

- Work on a branch; the PR title is a conventional commit, `type(scope): subject`, for example
  `fix(loamz-core): retry on 504`. Scopes are listed in `.github/workflows/pr-title.yml`.
- Use `uv`, never `pip`.

```bash
uv sync --all-packages --all-groups
make lint imports test
```

- Clients stay thin: no package here may import `loamz.engine` or `loamz.server` (`make imports` enforces it).
- Naming follows the Azure SDK guidelines: `<Service>Client(endpoint, credential)`, `list_*` returns a pager,
  `begin_*` returns a poller, errors derive from `HttpResponseError`.
- Nothing is deployed yet, so there is no backward-compatibility burden: delete old code instead of shimming.
