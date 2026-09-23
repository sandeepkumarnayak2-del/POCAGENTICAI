# Agentic Upgrade Notes

This version keeps the existing working service-desk architecture but makes
the agent layer modular and adds an LLM-only agent-to-agent workflow.

## Changes

1. Split the previous large `app/agents/agents.py` into focused modules:
   `base.py`, `schemas.py`, `supervisor.py`, `knowledge.py`,
   `investigation.py`, `ticket.py`, `action.py`, and `general.py`.
2. Kept `app/agents/agents.py` as a small compatibility facade so existing
   imports continue to work.
3. Removed Tavily and all web-search code. No internet search is performed.
4. Added `InvestigationAgent`, which uses only the configured LLM.
5. Added Knowledge -> Investigation handoff when internal RAG evidence is
   insufficient for an investigation-style request.
6. Added Investigation -> Action routing when the user requests a ticket/action.
7. Kept human approval before consequential ticket creation.
8. Kept MCP for ticket execution and existing authorization/idempotency logic.
9. Added a safe Action Agent fallback when Groq structured function calling
   fails, preventing a 500 while still requiring human approval.
10. Added regression tests for modularity, handoffs, no-web-search behavior,
    MCP, HITL, checkpointing, and the safe action fallback.

No external web-search API key is required.
