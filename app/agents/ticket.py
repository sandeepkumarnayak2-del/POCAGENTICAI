"""Ticket investigation agent backed by MCP."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool

from .base import AgentResult, BaseAgent, clean_response
from app.config import settings
from app.llm.provider import SYSTEM
from app.mcp.client import call_tool_sync
from app.observability.metrics import TOOL_CALLS
from app.observability.logging import logger
from app.tools.ticket_tools import TICKET_TOOLS


class TicketAgent(BaseAgent):
    name = "ticket"

    def __init__(self, llm=None):
        super().__init__(llm=llm, tools=[])

    @staticmethod
    def _mcp_tools(username: str, role: str) -> list[BaseTool]:
        @tool
        def search_my_tickets() -> list[dict]:
            """Search tickets visible to the authenticated user."""
            return call_tool_sync(
                "search_my_tickets",
                {
                    "username": username,
                    "role": role,
                },
            )

        @tool
        def get_my_ticket(ticket_id: int) -> dict:
            """Get one ticket visible to the authenticated user."""
            return call_tool_sync(
                "get_ticket_for_user",
                {
                    "ticket_id": ticket_id,
                    "username": username,
                    "role": role,
                },
            )

        return [search_my_tickets, get_my_ticket]

    def run(
        self,
        message: str,
        username: str,
        role: str,
        prior_messages: list[Any] | None = None,
    ) -> AgentResult:

        # ---------------------------------------------------------
        # 1. Build short-term conversation history
        # ---------------------------------------------------------
        # Keep the current request separate from checkpoint history.
        # The authenticated identity is always supplied by the app.
        history = []

        for item in (prior_messages or [])[-6:]:
            item_type = getattr(item, "type", "")
            content = getattr(item, "content", "")

            if not content:
                continue

            if item_type == "human" and content != message:
                history.append(HumanMessage(content=content))

            elif item_type == "ai":
                # Keep only the assistant's natural-language response.
                # Do not replay previous tool_calls into Groq.
                history.append(AIMessage(content=content))

        messages = [
            *history,
            HumanMessage(content=message),
        ]

        # ---------------------------------------------------------
        # 2. Prepare tools
        # ---------------------------------------------------------
        tools = (
            self._mcp_tools(username, role)
            if settings.mcp_enabled
            else TICKET_TOOLS
        )

        tool_llm = self.llm.bind_tools(tools)

        transport = "mcp" if settings.mcp_enabled else "local"

        # Track tools that have already returned a successful result.
        # This prevents the LLM from repeatedly calling the same
        # read-only tool with the same purpose.
        successful_tools: set[str] = set()

        # Maximum number of agent/tool reasoning rounds.
        max_iterations = 3

        # ---------------------------------------------------------
        # 3. Agent / tool loop
        # ---------------------------------------------------------
        for iteration in range(max_iterations):

            system_prompt = f"""{SYSTEM}

You are the Ticket Agent for an enterprise helpdesk.

Your job is to investigate EXISTING tickets and answer the user's CURRENT request.

Rules:

1. Use ticket tools when ticket information is required.

2. After receiving a tool result, inspect that result carefully.

3. If the tool result contains enough information to answer the user's
   request, STOP calling tools and answer the user.

4. Do not call the same read-only tool again if it already returned
   useful information.

5. Only call another tool when the existing information is insufficient
   to answer the current request.

6. Never create, modify, close, or delete tickets.

7. Never invent ticket information.

8. Never access another user's tickets.

9. The authenticated identity is:
   username={username}
   role={role}

10. Do not ask the user for their username. The application already
    provides the authenticated identity.

11. Focus only on the CURRENT request.

12. If the user asks for a list of their tickets, one successful
    search_my_tickets result is normally sufficient. Summarize that
    result instead of searching again.

Transport: {transport}
"""

            ai = tool_llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    *messages,
                ]
            )

            messages.append(ai)

            calls = getattr(ai, "tool_calls", [])

            # -----------------------------------------------------
            # No tool call -> final answer
            # -----------------------------------------------------
            if not calls:
                return AgentResult(
                    clean_response(ai.content),
                    messages,
                    {
                        "tool_iterations": iteration,
                        "tool_transport": transport,
                    },
                )

            # -----------------------------------------------------
            # Process tool calls
            # -----------------------------------------------------
            for call in calls:

                tool_name = call["name"]

                selected = next(
                    (t for t in tools if t.name == tool_name),
                    None,
                )

                # -------------------------------------------------
                # Duplicate successful tool call protection
                # -------------------------------------------------
                if tool_name in successful_tools:
                    logger.info(
                        "agent_duplicate_tool_call_blocked",
                        agent="ticket",
                        tool=tool_name,
                        username=username,
                    )

                    messages.append(
                        ToolMessage(
                            content=json.dumps(
                                {
                                    "error": "duplicate_tool_call",
                                    "message": (
                                        f"{tool_name} already returned "
                                        "a successful result. "
                                        "Use the existing result to "
                                        "answer the user."
                                    ),
                                }
                            ),
                            tool_call_id=call["id"],
                            name=tool_name,
                        )
                    )

                    continue

                try:

                    if not selected:
                        result = {
                            "error": "unknown_tool",
                            "tool": tool_name,
                        }

                    else:
                        args = dict(call.get("args", {}))

                        # Local tools need the authenticated identity
                        # explicitly. MCP tools already have username
                        # and role captured in their closure.
                        if not settings.mcp_enabled:
                            args.update(
                                username=username,
                                role=role,
                            )

                        logger.info(
                            "agent_tool_call",
                            agent="ticket",
                            tool=tool_name,
                            action="ticket_lookup",
                            username=username,
                        )

                        result = selected.invoke(args)

                        # Only mark the tool as successful after the
                        # tool actually returned successfully.
                        successful_tools.add(tool_name)

                        TOOL_CALLS.labels(
                            tool_name,
                            "success",
                        ).inc()

                except Exception as exc:

                    TOOL_CALLS.labels(
                        tool_name,
                        "error",
                    ).inc()

                    logger.exception(
                        "agent_tool_call_failed",
                        agent="ticket",
                        tool=tool_name,
                        username=username,
                    )

                    result = {
                        "error": "tool_failed",
                        "detail": str(exc),
                        "transport": transport,
                    }

                # -------------------------------------------------
                # Give the tool result back to the LLM
                # -------------------------------------------------
                messages.append(
                    ToolMessage(
                        content=json.dumps(
                            result,
                            default=str,
                        ),
                        tool_call_id=call["id"],
                        name=tool_name,
                    )
                )

        # ---------------------------------------------------------
        # 4. Safety fallback
        # ---------------------------------------------------------
        return AgentResult(
            "I could not complete the ticket investigation safely.",
            messages,
            {
                "tool_iterations": max_iterations,
                "tool_transport": transport,
            },
        )