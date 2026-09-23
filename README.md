# POCAI — Enterprise AI Service Desk Agent

POCAI is a proof-of-concept AI service desk agent demonstrating RAG, agent workflows, secure tool execution, authorization, human approval, and production-oriented observability.

## Overview

The application can:

- Answer IT support questions using RAG
- Retrieve information from internal IT documentation
- Create, list, and retrieve service desk tickets
- Require human approval before ticket creation
- Enforce JWT authentication and role-based access
- Enforce object-level ticket authorization
- Protect against basic prompt-injection attempts
- Validate and sanitize user input
- Store application data in PostgreSQL
- Use a Redis-compatible Key Value service for rate limiting and shared state
- Provide health checks, metrics, logging, and audit events

## Architecture

```text
User
  |
  v
FastAPI
  |
  +-- Authentication / RBAC
  |
  v
LangGraph Agent
  |
  +-- RAG ------> Chroma ------> IT Documentation
  |
  +-- Tools ----> Ticket Operations
  |
  +-- MCP -------> External Services
  |
  v
Human Approval
  |
  v
PostgreSQL
  |
  v
Response
```

## Technology

- Python
- FastAPI
- LangGraph
- LangChain
- Groq / GPT-OSS
- Chroma
- PostgreSQL
- Redis-compatible Key Value
- JWT
- Docker
- Render
- Prometheus

## Observability

- Health check: `/health`
- Prometheus metrics: `/metrics`
- Structured application logging
- Audit events
- LLM latency and call metrics
- Tool-call metrics

## Security

Authorization is enforced by application code rather than relying on the LLM.

Users can only access tickets they are authorized to view.

Consequential actions require human approval before execution.

Sensitive configuration such as API keys is stored as environment variables and is not committed to the repository.

## Example Workflow

```text
User: My VPN is not working
        |
        v
RAG retrieves relevant IT documentation
        |
        v
User: Create a high-priority ticket
        |
        v
Human approval required
        |
        v
Approved
        |
        v
Ticket created in PostgreSQL
```

## Live Demo

https://enterprise-ai-agent-api.onrender.com/

## API Documentation

https://enterprise-ai-agent-api.onrender.com/docs

## Local Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Application:

```text
http://localhost:8000/
```

API documentation:

```text
http://localhost:8000/docs
```

## Project Structure

```text
app/
├── agents/          # Modular LangGraph agents and orchestration
├── auth/            # Authentication
├── database/        # Database models and setup
├── llm/             # LLM provider
├── observability/   # Logging, metrics and audit
├── rag/             # RAG implementation
├── security/        # Validation and guardrails
├── tools/           # Service desk tools
└── mcp/             # MCP server

frontend/             # Web UI
data/documents/       # IT knowledge documents
tests/                # Automated tests
docs/                 # Architecture and deployment docs
```

## Agentic workflow

The project uses separate LLM-backed agents with explicit LangGraph handoffs:

```text
Supervisor
   |
   +--> Knowledge Agent --> Internal RAG
   |          |
   |          +--> insufficient evidence --> Investigation Agent (LLM only)
   |                                                    |
   |                                                    +--> Action Agent
   |                                                         |
   |                                                    Human Approval
   |                                                         |
   |                                                         +--> MCP
   |
   +--> Ticket Agent --> MCP
   |
   +--> General Agent
   ```

There is **no internet/web-search integration**. The Investigation Agent uses
the configured LLM only and must not claim external verification.

## Future Improvements

- Enterprise SSO / OAuth2
- ServiceNow or Jira integration
- Improved RAG evaluation
- Distributed tracing
- Advanced security testing
- Production vector database
- Model and prompt evaluation
