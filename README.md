# loamz-python

Python client libraries for Loamz, with one consistent naming standard: one namespace (`loamz`), one
distribution per service.

| Distribution | Import | What it is |
| --- | --- | --- |
| `loamz-core` | `loamz.core` | transport, retries, errors (`HttpResponseError`), paging (`ItemPaged`), long-running operations (`LROPoller`), tenancy rules |
| `loamz-identity` | `loamz.identity` | credentials: `DefaultLoamzCredential`, `ClientSecretCredential` |
| `loamz-data` | `loamz.data` | `DataClient(endpoint, credential, workspace=…)`: governed SQL and the catalog of one workspace (sync and `loamz.data.aio`) |
| `loamz` | | installs all of the above |

```python
from loamz.data import DataClient
from loamz.identity import DefaultLoamzCredential

client = DataClient("https://data.example.com", DefaultLoamzCredential(), workspace=workspace_id)
df = client.sql("SELECT region, count(*) AS n FROM shop.main.sales GROUP BY 1")
```

Clients are thin: they call the API and never import an engine or a server (enforced by `.importlinter`). The open
server lives in [loamz/loamz-server](https://github.com/loamz/loamz-server).

```bash
uv sync --all-packages --all-groups
make lint imports test
```

Apache-2.0.
