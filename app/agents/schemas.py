"""Structured decisions shared by agents."""
from typing import Literal
from pydantic import BaseModel, Field

class RoutingDecision(BaseModel):
    agent: Literal["knowledge", "ticket", "action", "general", "investigation"] = Field(
        description="Specialist owning the request."
    )
    reason: str = Field(description="Short routing reason.")

class TicketActionPlan(BaseModel):
    title: str = Field(description="Short ticket title based only on the request.")
    description: str = Field(description="Clear issue description using only known facts.")
    priority: Literal["low", "medium", "high"] = Field(description="Requested or safely inferred priority.")
    reason: str = Field(description="Why the action is being proposed.")
