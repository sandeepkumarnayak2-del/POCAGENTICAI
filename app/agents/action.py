"""Consequential-action planning agent."""
from __future__ import annotations
from langchain_core.messages import HumanMessage, SystemMessage
from .base import BaseAgent
from .schemas import TicketActionPlan
from app.llm.provider import SYSTEM
from app.observability.logging import logger

class ActionAgent(BaseAgent):
    name = "action"
    def __init__(self, llm=None):
        super().__init__(llm=llm)
        self.planner = self.llm.with_structured_output(TicketActionPlan, method="function_calling")

    @staticmethod
    def _fallback(message: str) -> dict[str, str]:
        text = message.strip()
        lower = text.lower()
        priority = "high" if "high priority" in lower or "urgent" in lower else "medium"
        title = "IT Support Request"
        if "vpn" in lower:
            title = "VPN Connectivity Issue"
        elif "outlook" in lower:
            title = "Outlook Support Request"
        return {
            "title": title,
            "description": f"User reported: {text}",
            "priority": priority,
            "reason": "Prepared from the user's request after structured planning was unavailable. Human approval is still required.",
        }

    def plan(self, message: str, conversation: str = "") -> dict[str, str]:
        try:
            result = self.planner.invoke([
                SystemMessage(content=f"""{SYSTEM}

You are the Action Agent.
Prepare a ticket creation plan only. NEVER execute it.
Extract only facts explicitly provided by the user or supported by the conversation.
Do not invent impact, urgency, credentials, systems, or business facts.
Human approval is mandatory before execution.
Return only TicketActionPlan.
"""),
                HumanMessage(content=f"""Relevant conversation:
{conversation or '[none]'}

CURRENT REQUEST:
{message}"""),
            ])
            return {"title": result.title, "description": result.description, "priority": result.priority, "reason": result.reason}
        except Exception as exc:
            logger.warning(
                "action_plan_fallback",
                action="prepare_ticket_plan",
                error_type=type(exc).__name__,
            )
            return self._fallback(message)
