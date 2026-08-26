# Backend

The backend contains five independently running services:

| Service | Port |
|---|---:|
| HR/Business MCP | 8111 |
| Product/Order MCP | 8112 |
| HR/Business A2A | 8211 |
| Product/Order A2A | 8212 |
| LangGraph Host API | 8311 |

Install dependencies from the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

The public API is `POST /chat`. All other services are internal protocol
layers. See the root [README](../README.md) for architecture, individual start
commands, tests, SDK adaptations, and interview explanations.
