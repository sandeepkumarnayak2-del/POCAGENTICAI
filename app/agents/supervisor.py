"""Supervisor/router agent."""
from __future__ import annotations
from langchain_core.messages import HumanMessage, SystemMessage
from .base import BaseAgent
from .utils import direct_route
from app.observability.logging import logger
from .schemas import RoutingDecision
from app.llm.provider import SYSTEM

class SupervisorAgent(BaseAgent):
    name = "supervisor"
    def __init__(self, llm=None):
        super().__init__(llm=llm)
        self.router = self.llm.with_structured_output(RoutingDecision, method="function_calling")

    def decide(self, message: str, conversation: str = "") -> dict[str, str]:
        direct = direct_route(message)
        if direct:
            logger.info(
                "agent_route",
                from_agent="supervisor",
                to_agent=direct,
                reason="deterministic_read_only_route",
                action="route_request",
            )
            return {"agent": direct, "reason": "Deterministic route for an unambiguous own-ticket lookup."}

        result = self.router.invoke([
            SystemMessage(content=f"""{SYSTEM}

You are the Supervisor Agent for an enterprise IT service desk. You ONLY route.
Select exactly one: knowledge, ticket, action, general, investigation.

Routing rules:
- knowledge: internal IT troubleshooting, company documentation, policies, procedures.
- ticket: list/read/status of existing tickets.
- action: explicit request to create/modify/close a ticket immediately.
- general: greetings, casual conversation, unrelated general questions.
- investigation: explicit investigation/analysis that does not primarily require internal RAG, or an external/current-information request. This does NOT perform internet search.

IMPORTANT: If a user reports an IT problem and says "check internal documentation first" or "if documentation is insufficient, investigate/research and then prepare a ticket if necessary", route to KNOWLEDGE. The graph will decide whether to hand off to INVESTIGATION and then ACTION.

Examples:
"Show my tickets" => ticket
"Create a ticket for my VPN problem" => action
"My VPN is not working" => knowledge
"My VPN is not working. Check internal docs first; if insufficient, investigate and prepare a ticket if necessary" => knowledge
"Analyze this error" => investigation
"Hello" => general

Never answer the user. Return only RoutingDecision.
"""),
            HumanMessage(content=f"""Recent conversation:
{conversation or '[none]'}

CURRENT REQUEST:
{message}"""),
        ])
        logger.info(
            "agent_route",
            from_agent="supervisor",
            to_agent=result.agent,
            reason=result.reason,
            action="route_request",
        )
        return {"agent": result.agent, "reason": result.reason}
