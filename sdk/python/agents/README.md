# loamz-agents

Client for Loamz Agents: create agents, open threads, invoke an agent and stream the run, answer approvals.

```python
from loamz.agents import AgentsClient
from loamz.identity import DefaultLoamzCredential

client = AgentsClient("https://agents.example.com", DefaultLoamzCredential())
agent = client.create_agent("analyst", instructions="Answer questions about taxi trips.")
thread = client.create_thread(agent_id=agent["id"])
for event in client.invoke_agent(thread["id"], "How many trips in June?"):
    print(event.text, end="")
```

`list_*` return lazy pagers; `loamz.agents.aio.AgentsClient` is the asyncio client.
