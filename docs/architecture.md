# Architecture

## Overview

The service desk uses FastAPI for the API boundary and LangGraph for stateful
multi-agent orchestration.

```text
User
  |
  v
FastAPI
  |
  +-- Authentication / RBAC
  +-- Validation / Guardrails / Rate Limit
  |
  v
LangGraph
  |
  v
Supervisor Agent
  |
  v
Recall Long-term Memory
  |
  +-- Knowledge Agent ----> Internal RAG / Chroma
  |          |
  |          +-- insufficient evidence --> Investigation Agent
  |                                             |
  |                                             +-- needs action --> Action Agent
  |
  +-- Ticket Agent --------> MCP ---------> Ticket System
  |
  +-- General Agent
  |
  +-- Action Agent --------> Human Approval --> MCP --> Ticket System
```

## Agent responsibilities

- **SupervisorAgent**: LLM-based routing only.
- **KnowledgeAgent**: enterprise IT knowledge and RAG. It can hand off when internal evidence is insufficient for an investigation request.
- **InvestigationAgent**: LLM-only analysis after a knowledge handoff. It has **no internet/search tool** and must not claim external verification.
- **TicketAgent**: reads existing tickets through MCP and respects authenticated identity/role.
- **ActionAgent**: prepares consequential ticket actions. It never executes them directly. The stored plan is resumed through the HITL checkpoint only after approval.
- **GeneralAgent**: handles greetings and general non-service-desk questions.

## Agentic handoff

The key multi-agent workflow is:

```text
Supervisor
    |
    v
Knowledge Agent
    |
    +-- sufficient evidence --> answer
    |
    +-- insufficient evidence
              |
              v
       Investigation Agent
              |
              +-- no action --> answer
              |
              +-- action requested
                       |
                       v
                 Action Agent
                       |
                       v
                 Human Approval
                       |
                       +-- reject --> end
                       |
                       +-- approve --> MCP --> ticket
```

This is intentionally LLM-only for investigation. There is no Tavily, web
search API, or external search dependency.

## Memory

- Short-term memory: LangGraph state/checkpoint keyed by the user's thread.
- Long-term memory: user-scoped SQL `Memory` records.

## Production notes

Local development uses SQLite for application/checkpoint state. Production
should use PostgreSQL-backed persistence for durable workflow state and
application data. A persistent vector store should be used instead of an
`/tmp` Chroma directory for production RAG.
