"""LangGraph orchestration for the real multi-agent IT service desk."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Literal

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agents.agents import (
    ActionAgent,
    GeneralAgent,
    KnowledgeAgent,
    SupervisorAgent,
    TicketAgent,
    InvestigationAgent,
)
from app.agents.state import AgentState
from app.database.db import SessionLocal
from app.database.models import Approval
from app.memory import recall_memories, save_explicit_memory
from app.security.guardrails import detect_prompt_injection
from app.mcp.client import call_tool_sync
from app.observability.logging import logger

BASE_DIR = Path(__file__).resolve().parents[2]
_conn = sqlite3.connect(BASE_DIR / "checkpoints.sqlite", check_same_thread=False)
checkpointer = SqliteSaver(_conn)

_agents = None


def _get_agents():
    global _agents
    if _agents is None:
        _agents = {
            "supervisor": SupervisorAgent(),
            "knowledge": KnowledgeAgent(),
            "investigation": InvestigationAgent(),
            "ticket": TicketAgent(),
            "general": GeneralAgent(),
            "action": ActionAgent(),
        }
    return _agents


def _conversation(state: AgentState, limit: int = 8) -> str:
    """Build clean conversational context without internal tool payloads."""
    messages = state.get("messages", [])
    lines = []

    for message in messages[-limit:]:
        message_type = getattr(message, "type", "user")
        content = getattr(message, "content", str(message))

        if not content or message_type == "tool":
            continue

        if message_type == "human":
            role = "user"
        elif message_type == "ai":
            role = "assistant"
        else:
            role = message_type

        lines.append(f"{role}: {content}")

    return "\n".join(lines)


def supervisor_node(state: AgentState):
    logger.info(
        "agent_start",
        agent="supervisor",
        username=state["username"],
        thread_id=state["thread_id"],
        action="route_request",
    )
    decision = _get_agents()["supervisor"].decide(
        state["message"],
        _conversation(state),
    )
    logger.info(
        "agent_handoff",
        from_agent="supervisor",
        to_agent=decision["agent"],
        reason=decision["reason"],
        username=state["username"],
        thread_id=state["thread_id"],
    )
    return {"agent": decision["agent"], "intent": decision["reason"]}


def recall_node(state: AgentState):
    return {"memories": recall_memories(state["username"], state["message"])}


def knowledge_node(state: AgentState):
    logger.info(
        "agent_start",
        agent="knowledge",
        username=state["username"],
        thread_id=state["thread_id"],
        action="internal_rag",
    )
    result = _get_agents()["knowledge"].run(
        state["message"],
        state.get("memories", []),
        _conversation(state),
    )
    if result.metadata.get("handoff"):
        logger.info(
            "agent_handoff",
            from_agent="knowledge",
            to_agent=result.metadata["handoff"],
            reason="insufficient_internal_evidence",
            username=state["username"],
            thread_id=state["thread_id"],
        )
    else:
        logger.info(
            "agent_complete",
            agent="knowledge",
            action="answer_from_internal_knowledge",
            username=state["username"],
            thread_id=state["thread_id"],
        )
    return {
        "response": result.response,
        **result.metadata,
        "messages": result.messages,
    }


def investigation_node(state: AgentState):
    logger.info(
        "agent_start",
        agent="investigation",
        username=state["username"],
        thread_id=state["thread_id"],
        action="llm_only_analysis",
    )
    result = _get_agents()["investigation"].run(
        state["message"],
        state.get("memories", []),
        _conversation(state),
        state.get("documents", []),
    )
    if result.metadata.get("needs_action"):
        logger.info(
            "agent_handoff",
            from_agent="investigation",
            to_agent="action",
            reason="explicit_action_requested",
            username=state["username"],
            thread_id=state["thread_id"],
        )
    else:
        logger.info(
            "agent_complete",
            agent="investigation",
            action="analysis_complete_no_action",
            username=state["username"],
            thread_id=state["thread_id"],
        )
    return {
        "response": result.response,
        **result.metadata,
        "agent": "investigation",
        "messages": result.messages,
    }


def ticket_node(state: AgentState):
    logger.info(
        "agent_start",
        agent="ticket",
        username=state["username"],
        thread_id=state["thread_id"],
        action="ticket_lookup",
    )
    result = _get_agents()["ticket"].run(
        state["message"],
        state["username"],
        state["role"],
        state.get("messages", []),
    )
    logger.info(
        "agent_complete",
        agent="ticket",
        action="ticket_lookup_complete",
        username=state["username"],
        thread_id=state["thread_id"],
    )
    return {
        "response": result.response,
        **result.metadata,
        "messages": result.messages,
    }


def general_node(state: AgentState):
    result = _get_agents()["general"].run(
        state["message"],
        _conversation(state),
        state.get("memories", []),
    )
    return {"response": result.response, "messages": result.messages}

def plan_action_node(state: AgentState):
    logger.info(
        "agent_start",
        agent="action",
        username=state["username"],
        thread_id=state["thread_id"],
        action="prepare_ticket_plan",
    )
    plan = _get_agents()["action"].plan(
        state["message"],
        _conversation(state),
    )
    db = SessionLocal()
    try:
        row = Approval(
            username=state["username"],
            action="create_ticket",
            payload=json.dumps({"message": state["message"], "plan": plan}),
            thread_id=state["thread_id"],
            status="pending",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info(
            "human_approval_required",
            approval_id=row.id,
            username=state["username"],
            thread_id=state["thread_id"],
            action="create_ticket",
            priority=plan["priority"],
        )
        return {
            "approval_id": row.id,
            "action": {"type": "create_ticket", **plan},
        }
    finally:
        db.close()


def approval_node(state: AgentState):
    decision = interrupt(
        {
            "type": "approval_required",
            "approval_id": state["approval_id"],
            "action": state["action"],
            "message": "The Action Agent prepared this ticket. Approve to execute it or reject to cancel.",
        }
    )
    if bool(decision):
        return Command(
            goto="execute_action",
            update={"response": "Approval received."},
        )
    return Command(
        goto="reject_action",
        update={"response": "Approval rejected."},
    )


def execute_action_node(state: AgentState):
    db = SessionLocal()
    try:
        approval = db.get(Approval, state["approval_id"])
        if not approval or approval.status != "pending":
            return {"response": "This approval is no longer pending."}

        payload = json.loads(approval.payload)
        plan = payload["plan"]

        logger.info(
            "action_execute",
            agent="action",
            username=state["username"],
            thread_id=state["thread_id"],
            action="create_ticket",
            approval_id=approval.id,
        )
        result = call_tool_sync(
            "create_ticket_for_user",
            {
                "username": state["username"],
                "role": state["role"],
                "title": plan["title"],
                "description": plan["description"],
                "priority": plan["priority"],
                "idempotency_key": f"approval-{approval.id}",
            },
        )

        if not isinstance(result, dict) or result.get("error"):
            return {
                "response": (
                    "Ticket creation failed: "
                    f"{result.get('error', 'invalid MCP response') if isinstance(result, dict) else 'invalid MCP response'}"
                )
            }

        approval.status = "approved"
        db.commit()
        logger.info(
            "action_complete",
            agent="action",
            username=state["username"],
            thread_id=state["thread_id"],
            action="create_ticket",
            ticket_id=result["id"],
        )
        return {
            "response": f"Ticket #{result['id']} was created successfully.",
            "action": {"ticket": result},
        }
    finally:
        db.close()


def reject_action_node(state: AgentState):
    db = SessionLocal()
    try:
        approval = db.get(Approval, state["approval_id"])
        if approval and approval.status == "pending":
            approval.status = "rejected"
            db.commit()
        logger.info(
            "action_rejected",
            agent="action",
            username=state["username"],
            thread_id=state["thread_id"],
            action="create_ticket",
            approval_id=state["approval_id"],
        )
        return {"response": "The ticket creation request was rejected."}
    finally:
        db.close()


def route(
    state: AgentState,
) -> Literal["knowledge", "investigation", "ticket", "general", "plan_action"]:
    return {
        "knowledge": "knowledge",
        "investigation": "investigation",
        "ticket": "ticket",
        "general": "general",
        "action": "plan_action",
    }[state["agent"]]


def route_after_knowledge(state: AgentState) -> Literal["investigation", "end"]:
    """Hand off to Investigation when internal RAG evidence is insufficient."""
    return "investigation" if state.get("handoff") == "investigation" else "end"


def route_after_investigation(state: AgentState) -> Literal["plan_action", "end"]:
    """Only proceed to consequential planning when action is requested."""
    return "plan_action" if state.get("needs_action") else "end"


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("supervisor", supervisor_node)
    builder.add_node("recall", recall_node)
    builder.add_node("knowledge", knowledge_node)
    builder.add_node("investigation", investigation_node)
    builder.add_node("ticket", ticket_node)
    builder.add_node("general", general_node)
    builder.add_node("plan_action", plan_action_node)
    builder.add_node("approval", approval_node)
    builder.add_node("execute_action", execute_action_node)
    builder.add_node("reject_action", reject_action_node)

    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", "recall")

    builder.add_conditional_edges(
        "recall",
        route,
        {
            "knowledge": "knowledge",
            "investigation": "investigation",
            "ticket": "ticket",
            "general": "general",
            "plan_action": "plan_action",
        },
    )

    # Agent-to-agent handoff: Knowledge -> Investigation when internal
    # evidence is insufficient. Investigation uses the LLM only; no web tool.
    builder.add_conditional_edges(
        "knowledge",
        route_after_knowledge,
        {
            "investigation": "investigation",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "investigation",
        route_after_investigation,
        {
            "plan_action": "plan_action",
            "end": END,
        },
    )

    builder.add_edge("ticket", END)
    builder.add_edge("general", END)
    builder.add_edge("plan_action", "approval")
    builder.add_edge("execute_action", END)
    builder.add_edge("reject_action", END)

    return builder.compile(checkpointer=checkpointer)


graph = build_graph()


def _normalize(result):
    interrupts = result.get("__interrupt__")
    if interrupts:
        item = interrupts[0].value
        return {
            **result,
            "response": f"Approval required before creating a ticket. Approval ID: {item['approval_id']}",
            "approval_id": item["approval_id"],
            "interrupted": True,
        }
    return {**result, "interrupted": False}


def run_agent(username: str, role: str, message: str, thread_id: str):
    if detect_prompt_injection(message):
        logger.warning(
            "guardrail_block",
            username=username,
            thread_id=thread_id,
            action="prompt_injection_blocked",
        )
        return {
            "response": "I can't help with bypassing instructions or revealing sensitive information.",
            "approval_id": None,
            "interrupted": False,
        }

    save_explicit_memory(username, message)

    result = graph.invoke(
        {
            "username": username,
            "role": role,
            "thread_id": thread_id,
            "message": message,
            "messages": [("human", message)],
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    normalized = _normalize(result)
    logger.info(
        "workflow_complete",
        username=username,
        thread_id=thread_id,
        agent=normalized.get("agent"),
        handoff=normalized.get("handoff"),
        interrupted=normalized.get("interrupted"),
        action="chat_complete",
    )
    return normalized


def resume_agent(thread_id: str, approved: bool):
    logger.info(
        "human_approval_decision",
        thread_id=thread_id,
        approved=approved,
        action="resume_workflow",
    )
    result = graph.invoke(
        Command(resume=approved),
        config={"configurable": {"thread_id": thread_id}},
    )
    return _normalize(result)
