"""Shared primitives for specialist agents."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from app.llm.provider import get_llm, SYSTEM
from app.security.guardrails import output_guardrail

@dataclass
class AgentResult:
    response: str
    messages: list[Any]
    metadata: dict[str, Any]

class BaseAgent:
    name = "base"
    def __init__(self, llm=None, tools: list[BaseTool] | None = None):
        self.llm = llm or get_llm()
        self.tools = tools or []
    def system_prompt(self) -> str:
        return SYSTEM

def clean_response(content: Any) -> str:
    return output_guardrail(str(content or "").strip())
