# Enterprise Multi-Agent AI Assistant

A complete, locally runnable interview project showing how LangGraph, A2A,
Agno, and MCP divide responsibilities in an enterprise assistant. Users can
ask about HR policies, company information, products, inventory, and orders
through one conversational UI.

## Objective and business use case

Enterprise systems usually span several independently owned domains. Giving
one agent direct access to every database and API creates tight coupling and a
large, unreliable tool-selection surface. This project separates orchestration,
agent communication, domain reasoning, and data access:

```text
User
  |
  v
React frontend --HTTP--> FastAPI /chat
                            |
                            v
                     LangGraph Host
                   "Which remote agent?"
                         / A2A \
                        /       \
                       v         v
             HR/Business Agent  Product/Order Agent
                    |            Agent Executor
                    |                  |
                   MCP                Agno
                    |          "Which MCP tool?"
                    |                  |
                    +-------- MCP -----+
                             |
                  Products / Inventory / Orders
```

The Host never imports an MCP tool, reads enterprise data, or contains a
specialized agent implementation.

## Technology responsibilities

### LangGraph: Host orchestration

`backend/host/host_agent.py` defines a three-node graph:

1. `discover_agents` fetches remote Agent Cards.
2. `select_agent` compares the request with advertised skills and examples.
3. `delegate_with_a2a` sends the task through the A2A client.

This is where conversational routing happens. It answers **which remote
agent?**, not which database tool.

### A2A: agent-to-agent communication

Both remote agents expose:

- an Agent Card at `/.well-known/agent-card.json`;
- Agent Skills describing business functions;
- Agent Capabilities describing protocol features;
- a JSON-RPC A2A endpoint at `/a2a`;
- a `DefaultRequestHandler`;
- an `AgentExecutor`.

`backend/host/a2a_client.py` uses the official `A2ACardResolver`,
`ClientFactory`, and `SendMessageRequest` APIs. The Host sees names,
descriptions, endpoints, skills, examples, and capabilities. It does not see
remote implementation details.

### Agent Card, Skills, and Capabilities

An Agent Card answers: **who are you, where can I reach you, and what can you
do?**

The HR/Business card advertises:

- HR Policy Search
- Business Information Search

The Product/Order card advertises:

- Product Search
- Inventory Lookup
- Order Search
- Order Status

A **Skill** is a business function. A **Capability** is a protocol feature,
such as streaming or push notifications. This sample intentionally disables
both to keep the request flow clear.

### A2A Request Handler

`DefaultRequestHandler` receives protocol requests, creates a
`RequestContext`, interacts with the task store, and calls the configured
executor. It contains no business logic.

### Agent Executor: A2A-to-agent bridge

Each executor follows the reference pattern:

```text
RequestContext
  -> create A2A Task when needed
  -> TaskUpdater.start_work()
  -> connect domain agent to MCP
  -> invoke domain agent with context_id
  -> add A2A Artifact through EventQueue
  -> TaskUpdater.complete()
  -> close MCP resources
```

`RequestContext` carries the user message, task ID, and conversation context
ID. `EventQueue` carries task events back to the A2A server. `TaskUpdater`
creates status updates and result artifacts. The context ID becomes the Agno
session ID, while each request receives its own task ID.

The executor is an adapter. It does not implement tools, access JSON files, or
perform LLM reasoning.

### Agno: Product and Order reasoning

`backend/agents/product_order/mcp_agent.py` is the interview-friendly
`mcp_agent.py` layer:

1. configure Agno's MCP integration;
2. connect to the Product/Order MCP endpoint;
3. create an Agno `Agent` with a Gemini model;
4. make only the MCP-hosted tools visible to Agno;
5. invoke Agno with query and session/context ID;
6. normalize the `RunOutput`;
7. close the MCP connection.

Agno decides **which MCP tool should be invoked**. It never opens the JSON data
files. If no usable model credential is present, a small deterministic fallback
uses the same MCP contracts so the local demo remains runnable. The production
Agno path is used whenever Gemini completes successfully.

### MCP and FastMCP

MCP is the standardized agent-to-tool/data protocol. FastMCP owns the tool
implementations and exposes them over Streamable HTTP:

| Server | Endpoint | Tools |
|---|---|---|
| HR/Business | `http://127.0.0.1:8111/mcp` | `search_hr_policy`, `search_business_information` |
| Product/Order | `http://127.0.0.1:8112/mcp` | `search_products`, `check_inventory`, `get_order_status`, `search_orders` |

Streamable HTTP is used because agents connect to independently running MCP
services over HTTP rather than launching child STDIO processes.

Agno 3.0.1 provides `MCPTools`, the current one-server equivalent of the
reference implementation's `MultiMCPTools`. Additional MCP servers can be
represented by additional `MCPTools` instances in the Agno tool list.

### HR and business RAG

The transparent local RAG implementation is in `backend/rag/retriever.py`:

```text
Markdown documents
  -> 90-word overlapping chunks
  -> tokenization
  -> in-memory TF-IDF vector embeddings
  -> cosine similarity
  -> top relevant chunks
  -> Gemini answer (or retrieved-context fallback)
```

This deliberately avoids a vector database and a large RAG framework. The MCP
server owns retrieval; the Host does not know where or how documents are
stored.

### Frontend/backend boundary

The React frontend in `frontend/` calls only:

```http
POST /chat
Content-Type: application/json

{
  "message": "What is the status of order ORD1001?",
  "session_id": "optional-existing-session"
}
```

Response:

```json
{
  "response": "Order ORD1001 is Pending...",
  "session_id": "..."
}
```

The frontend never calls MCP, Agno, or either A2A server.

## End-to-end request flow

For “How many laptops are in stock?”:

1. React sends the message to `POST /chat`.
2. FastAPI passes it to the LangGraph Host.
3. The Host fetches both Agent Cards with `A2ACardResolver`.
4. Advertised Inventory Lookup metadata selects Product/Order.
5. `ClientFactory` sends an A2A `SendMessageRequest`.
6. `DefaultRequestHandler` builds a `RequestContext`.
7. `ProductOrderAgentExecutor` creates/updates the A2A task.
8. `ProductOrderMCPAgent` connects Agno to MCP with `MCPTools`.
9. Agno selects `check_inventory`.
10. FastMCP reads inventory data and returns the result.
11. Agno produces the user-facing answer.
12. The executor adds an artifact and marks the task complete.
13. A2A returns it to the Host, API, and frontend.

## Project structure

```text
backend/
  api/main.py
  host/
    host_agent.py
    a2a_client.py
  agents/
    hr_business/
      mcp_agent.py
      agent_executor.py
      a2a_server.py
    product_order/
      mcp_agent.py
      agent_executor.py
      a2a_server.py
  mcp_servers/
    hr_business_server.py
    product_order_server.py
  rag/retriever.py
  data/
    hr/ business/ products/ inventory/ orders/
  tests/
frontend/
```

## Setup

Requirements: Python 3.11+, Node.js 20+, and npm.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env

cd frontend
npm install
cd ..
```

Set `GEMINI_API_KEY` in `.env` to enable LLM routing and answer generation.
Never commit `.env`. The project still runs with deterministic local fallbacks
when the key is missing, denied, or rate-limited.

## Run all services

Open six terminals from the repository root:

```bash
# 1. HR/Business MCP — Streamable HTTP
.venv/bin/python -m backend.mcp_servers.hr_business_server

# 2. Product/Order MCP — Streamable HTTP
.venv/bin/python -m backend.mcp_servers.product_order_server

# 3. HR/Business A2A
.venv/bin/uvicorn backend.agents.hr_business.a2a_server:app \
  --host 0.0.0.0 --port 8211

# 4. Product/Order A2A
.venv/bin/uvicorn backend.agents.product_order.a2a_server:app \
  --host 0.0.0.0 --port 8212

# 5. LangGraph Host and public API
.venv/bin/uvicorn backend.api.main:app \
  --host 0.0.0.0 --port 8311

# 6. Frontend
cd frontend
npm run dev -- --host 0.0.0.0 --port 4311
```

Open `http://127.0.0.1:4311`.

## Tests

```bash
# Unit, RAG, tools, Host routing, and /chat API
cd backend
../.venv/bin/pytest -q

# With all backend services running: official A2A + MCP live flow
cd ..
.venv/bin/python backend/tests/live_e2e.py

# Frontend checks
cd frontend
npm run lint
npm run build
```

The live script validates:

- work-from-home policy → HR A2A → HR MCP → RAG;
- laptop stock → Product A2A → Agno/MCP → inventory;
- ORD1001 status → Product A2A → Agno/MCP → order status;
- P1001 details → Product A2A → Agno/MCP → product search.

## Example queries

- What is the work from home policy?
- What is the maternity leave policy?
- What is the travel reimbursement policy?
- What are the company's business units?
- Show me information about product P1001.
- Find products in the electronics category.
- How many laptops are currently in stock?
- Is product P1001 in stock?
- What is the status of order ORD1001?
- Show me pending orders.

## Error handling

- MCP connection errors become readable domain-service errors.
- A2A discovery/delegation failures are reported by the Host.
- Unknown intents list supported enterprise domains.
- Missing products, inventory, orders, and documents return explicit messages.
- Missing or unusable LLM credentials fall back to local retrieval/tool routing.

## SDK adaptations from the reference

The architecture follows the supplied guided project, but APIs were updated:

1. `a2a-sdk==1.1.2` uses protobuf messages, `supported_interfaces`, and FastAPI
   route helpers instead of the older Pydantic/Starlette application examples.
2. A2A v1 requires a `Task` as the first event before status/artifact updates.
3. Agno 3 removed `MultiMCPTools`; `MCPTools` is its current Streamable HTTP
   integration for one server.
4. Agno 3.0.1 is not compatible with MCP 2.x (`McpError` was renamed), so the
   project pins the newest compatible MCP 1.x release, which retains FastMCP.

## Design decisions and limitations

- JSON files make enterprise mock data easy to inspect and edit.
- TF-IDF vectors make every retrieval step explainable in an interview.
- Agent Card routing is metadata-driven; a production deployment could use an
  LLM classifier plus policy controls for dozens of agents.
- Storage and task state are in memory.
- There is no authentication, authorization, audit log, PII filtering,
  persistent chat history, or production observability.
- The deterministic no-key path is a demo fallback, not a replacement for
  production model-based tool selection.

## Interview explanation

### 30 seconds

> LangGraph is my Host orchestration layer. It discovers specialized remote
> agents through A2A Agent Cards and chooses which agent should handle a query.
> The Product and Order remote agent uses Agno to choose an MCP-hosted tool.
> FastMCP exposes data tools through Streamable HTTP. Agent Executor bridges
> A2A task handling with agent execution and returns the answer as an A2A
> artifact.

### 1 minute

> I built an enterprise assistant for HR policies, business information,
> products, inventory, and orders. I avoided one giant agent by separating two
> domain agents. A LangGraph Host fetches their A2A Agent Cards and routes a
> request from advertised skills. A2A handles agent-to-agent communication.
> The remote Agent Executor converts the RequestContext into domain-agent
> execution and manages TaskUpdater and EventQueue. For Product and Order,
> Agno sees only MCP-hosted tools and decides which tool to invoke. FastMCP owns
> tool and data access over Streamable HTTP. HR MCP tools perform simple RAG
> over policy documents. Results return as A2A artifacts to the Host and UI.

### 2 minutes

> The system has five clear layers. First, the React UI talks only to a FastAPI
> `/chat` endpoint. Second, a LangGraph Host runs discovery, selection, and
> delegation nodes. It uses A2A Agent Cards, so it knows capabilities and
> endpoints but not implementation details. Third, each A2A server has a
> request handler and Agent Executor. The executor receives RequestContext,
> creates the task, uses TaskUpdater to publish status and artifacts through
> EventQueue, and passes the context ID as the domain-agent session. Fourth,
> Agno performs Product/Order reasoning and tool selection. Finally, MCP
> standardizes tool access; FastMCP executes catalog, inventory, order, or RAG
> functions against mock enterprise data. This separation means A2A solves
> agent communication, MCP solves agent-to-tool communication, LangGraph
> decides where work goes, and Agno decides which domain tool runs.

### Difficult problems faced

- Adapting the reference A2A task flow to the current protobuf-based v1 SDK.
- Preserving task/context identity across A2A and Agno sessions.
- Connecting Agno to remote Streamable HTTP MCP tools while ensuring cleanup.
- Resolving the current Agno/MCP 2.x incompatibility without changing the
  architecture.
- Keeping the demo operational when external model access is unavailable.

### Why each component?

- **Why A2A?** It standardizes discovery, delegation, task identity, and result
  exchange between independently deployable agents.
- **Why MCP?** It standardizes tool/data access and prevents agents from
  directly depending on databases or file layouts.
- **Why Agno?** It gives the Product/Order agent model-driven selection among
  domain MCP tools.
- **Why LangGraph?** It makes Host discovery, routing, and delegation an
  explicit, extensible workflow.
- **Why Agent Executor?** A2A and Agno have different execution models; the
  executor adapts tasks, contexts, events, sessions, and results.
- **Why Agent Card?** It exposes identity, endpoint, protocol capabilities, and
  skills so the Host can route without knowing agent internals.
- **How does discovery scale?** Add another A2A base URL/configuration entry.
  The Host fetches its card and evaluates advertised skills; core delegation
  and remote implementation do not change.
