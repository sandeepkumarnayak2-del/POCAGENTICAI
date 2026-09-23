"""Compatibility facade for the modular specialist agents.

Implementations live in focused modules. Importing from app.agents.agents remains
supported so existing code and tests do not break.
"""
from .base import AgentResult, BaseAgent
from .schemas import RoutingDecision, TicketActionPlan
from .supervisor import SupervisorAgent
from .knowledge import KnowledgeAgent
from .investigation import InvestigationAgent
from .ticket import TicketAgent
from .action import ActionAgent
from .general import GeneralAgent

__all__ = [
    "AgentResult", "BaseAgent", "RoutingDecision", "TicketActionPlan",
    "SupervisorAgent", "KnowledgeAgent", "InvestigationAgent",
    "TicketAgent", "ActionAgent", "GeneralAgent",
]
