"""LLM-only investigation agent. No internet or external search."""
from __future__ import annotations
import json
from langchain_core.messages import HumanMessage, SystemMessage
from .base import AgentResult, BaseAgent, clean_response
from .utils import action_requested
from app.llm.provider import SYSTEM

class InvestigationAgent(BaseAgent):
    name = "investigation"
    def run(self, message: str, memories: list[dict], conversation: str = "", documents: list[dict] | None = None) -> AgentResult:
        evidence = json.dumps((documents or [])[:8], default=str)
        context = f"""Recent conversation:
{conversation}""" if conversation else ""
        result = self.llm.invoke([
            SystemMessage(content=f"""{SYSTEM}

You are the Investigation Agent.
Your role is to independently analyze an IT problem after the Knowledge Agent could not find sufficient internal evidence.
You do NOT have internet access and must never claim that you searched the web or verified current external information.
Use your general model knowledge only as analysis, clearly distinguish it from company-specific policy, and identify uncertainty.
If internal evidence is provided, treat it only as evidence and not as proof when it was already judged insufficient.
At the end, explain whether the user explicitly requested a ticket/action. Do not execute any action.

Internal evidence attempted:
{evidence}

{context}"""),
            HumanMessage(content=message),
        ])
        needs_action = action_requested(message)
        response = clean_response(result.content)
        return AgentResult(response, [result], {"needs_action": needs_action, "investigation": True})
