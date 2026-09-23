from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_project_has_real_agent_classes():
    text = (ROOT / "app/agents/agents.py").read_text()
    for cls in ("SupervisorAgent", "KnowledgeAgent", "InvestigationAgent", "TicketAgent", "GeneralAgent", "ActionAgent"):
        assert cls in text


def test_graph_has_agent_handoffs():
    text = (ROOT / "app/agents/graph.py").read_text()
    assert "SupervisorAgent" in text
    assert "KnowledgeAgent" in text
    assert "TicketAgent" in text
    assert "ActionAgent" in text
    assert "InvestigationAgent" in text
    assert '"knowledge": "knowledge"' in text
    assert '"investigation": "investigation"' in text
    assert '"ticket": "ticket"' in text


def test_checkpoint_and_interrupt():
    text = (ROOT / "app/agents/graph.py").read_text()
    assert "SqliteSaver" in text
    assert "interrupt(" in text
    assert "Command(resume=" in text
    assert "checkpointer=checkpointer" in text


def test_tool_identity_is_overridden_inside_agent():
    text = (ROOT / "app/agents/ticket.py").read_text()
    assert "args.update(username=username, role=role)" in text


def test_mcp_server_exposes_tools():
    text = (ROOT / "app/mcp/server.py").read_text()
    assert "FastMCP" in text
    assert "@mcp.tool()" in text


def test_frontend_persists_and_sends_thread_id():
    text = (ROOT / "frontend/app.js").read_text()
    assert "localStorage.getItem" in text
    assert "thread_id" in text and "threadId" in text


def test_long_term_memory_is_user_scoped():
    text = (ROOT / "app/memory.py").read_text()
    assert "Memory.username == username" in text


def test_mcp_client_exists_in_runtime_package():
    assert (ROOT / "app/mcp/client.py").exists()


def test_runtime_has_ticket_tools():
    text = (ROOT / "app/tools/ticket_tools.py").read_text()
    assert "@tool" in text
    assert "TICKET_TOOLS" in text
