"""LLM-callable ticket tools.

The model may supply identity fields in tool arguments, but the executor
overwrites them with the authenticated identity from graph state. This keeps
authorization outside the model's control.
"""
from langchain_core.tools import tool
from app.tools.tickets import list_tickets, get_ticket, serialize


@tool
def search_my_tickets(username: str = "", role: str = "employee") -> list[dict]:
    """List tickets belonging to the authenticated user."""
    return [serialize(t) for t in list_tickets(username, role)]


@tool
def get_my_ticket(ticket_id: int, username: str = "", role: str = "employee") -> dict:
    """Get one ticket after application-layer authorization."""
    ticket = get_ticket(ticket_id, username, role)
    if ticket == "FORBIDDEN":
        return {"error": "forbidden"}
    if not ticket:
        return {"error": "not_found"}
    return serialize(ticket)


TICKET_TOOLS = [search_my_tickets, get_my_ticket]
