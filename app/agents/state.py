from typing import TypedDict, Any, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    username: str
    role: str
    thread_id: str
    messages: Annotated[list, add_messages]
    message: str
    intent: str
    agent: str
    search_query: str
    documents: list[dict[str, Any]]
    needs_action: bool
    handoff: str | None
    memories: list[dict[str, Any]]
    response: str
    approval_id: int | None
    action: dict[str, Any]
    tool_iterations: int
