"""MCP server exposing the authorized service-desk capabilities.

Run locally with:
    MCP_TRANSPORT=stdio python -m app.mcp.server

For Streamable HTTP:
    MCP_TRANSPORT=streamable-http MCP_PORT=8001 python -m app.mcp.server
"""
import os

from mcp.server.fastmcp import FastMCP

from app.tools.tickets import list_tickets, get_ticket, create_ticket, serialize
from app.observability.logging import logger

MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

mcp = FastMCP(
    "enterprise-service-desk",
    host=MCP_HOST,
    port=MCP_PORT,
)


@mcp.tool()
def search_my_tickets(username: str, role: str = "employee") -> list[dict]:
    """List tickets visible to the authenticated user."""
    logger.info("mcp_server_tool_call", tool="search_my_tickets", username=username, role=role)
    result = [serialize(t) for t in list_tickets(username, role)]
    logger.info("mcp_server_tool_result", tool="search_my_tickets", count=len(result))
    return result


@mcp.tool()
def get_ticket_for_user(ticket_id: int, username: str, role: str = "employee") -> dict:
    """Get one ticket after application-layer authorization."""
    logger.info("mcp_server_tool_call", tool="get_ticket_for_user", ticket_id=ticket_id, username=username, role=role)
    ticket = get_ticket(ticket_id, username, role)
    if ticket == "FORBIDDEN":
        return {"error": "forbidden"}
    if not ticket:
        return {"error": "not_found"}
    result = serialize(ticket)
    logger.info("mcp_server_tool_result", tool="get_ticket_for_user", ticket_id=ticket_id)
    return result


@mcp.tool()
def create_ticket_for_user(
    username: str,
    title: str,
    description: str,
    priority: str = "medium",
    role: str = "employee",
    idempotency_key: str | None = None,
) -> dict:
    """Create a ticket for the authenticated user after approval.

    The MCP server is the execution boundary for consequential ticket creation.
    The caller supplies the already-authenticated application identity and an
    idempotency key so a retried/resumed workflow cannot create duplicates.
    """
    logger.info(
        "mcp_server_tool_call",
        tool="create_ticket_for_user",
        username=username,
        role=role,
        priority=priority,
        idempotency_key=idempotency_key,
    )

    if role == "user":
        role = "employee"
    if role not in {"employee", "helpdesk", "admin"}:
        return {"error": "forbidden"}
    if not title.strip() or not description.strip():
        return {"error": "invalid_request"}
    if priority not in {"low", "medium", "high"}:
        return {"error": "invalid_priority"}

    ticket = create_ticket(
        username,
        title.strip(),
        description.strip(),
        priority,
        idempotency_key=idempotency_key,
    )
    result = serialize(ticket)
    logger.info(
        "mcp_server_tool_result",
        tool="create_ticket_for_user",
        ticket_id=ticket.id,
    )
    return result


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport in {"streamable-http", "http"}:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
