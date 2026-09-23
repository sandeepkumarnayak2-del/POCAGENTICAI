from pathlib import Path


def test_modular_agent_classes_exist():
    modules = {
        "SupervisorAgent": "app/agents/supervisor.py",
        "KnowledgeAgent": "app/agents/knowledge.py",
        "InvestigationAgent": "app/agents/investigation.py",
        "TicketAgent": "app/agents/ticket.py",
        "ActionAgent": "app/agents/action.py",
        "GeneralAgent": "app/agents/general.py",
    }
    for cls, filename in modules.items():
        text = Path(filename).read_text()
        assert f"class {cls}" in text


def test_compatibility_facade_exports_agents():
    text = Path("app/agents/agents.py").read_text()
    assert "from .investigation import InvestigationAgent" in text
    assert "WebResearchAgent" not in text


def test_graph_contains_agent_handoff_and_interrupt_workflow():
    text = Path("app/agents/graph.py").read_text()
    assert "SupervisorAgent" in text
    assert "KnowledgeAgent" in text
    assert "InvestigationAgent" in text
    assert "TicketAgent" in text
    assert "ActionAgent" in text
    assert "route_after_knowledge" in text
    assert "route_after_investigation" in text
    assert '"investigation"' in text
    assert "interrupt(" in text
    assert "Command(resume=" in text
    assert "checkpointer=checkpointer" in text


def test_investigation_is_llm_only():
    text = Path("app/agents/investigation.py").read_text()
    assert "self.llm.invoke" in text
    assert "internet access" in text
    assert "search_web" not in text
    assert "TAVILY" not in text


def test_action_agent_has_safe_fallback():
    text = Path("app/agents/action.py").read_text()
    assert "with_structured_output" in text
    assert "except Exception" in text
    assert "_fallback" in text
    assert "Human approval" in text


def test_ticket_agent_has_real_tool_calling():
    text = Path("app/agents/ticket.py").read_text()
    assert "bind_tools" in text
    assert "tool_calls" in text
    assert "ToolMessage" in text


def test_runtime_agents_are_importable():
    from app.agents.agents import (
        SupervisorAgent,
        KnowledgeAgent,
        InvestigationAgent,
        TicketAgent,
        ActionAgent,
        GeneralAgent,
    )
    assert all(cls is not None for cls in (
        SupervisorAgent, KnowledgeAgent, InvestigationAgent,
        TicketAgent, ActionAgent, GeneralAgent,
    ))


def test_runtime_graph_is_checkpointed():
    from app.agents.graph import graph, checkpointer
    assert graph is not None
    assert checkpointer is not None


def test_ticket_agent_is_mcp_wired_by_default():
    ticket = Path("app/agents/ticket.py").read_text()
    client = Path("app/mcp/client.py").read_text()
    server = Path("app/mcp/server.py").read_text()
    config = Path("app/config.py").read_text()
    assert "call_tool_sync" in ticket
    assert "mcp_enabled" in ticket
    assert "search_my_tickets" in server
    assert "get_ticket_for_user" in server
    assert "create_ticket_for_user" in server
    assert "streamable_http_client" in client
    assert "mcp_server_url" in config


def test_consequential_ticket_creation_uses_mcp_after_approval():
    graph = Path("app/agents/graph.py").read_text()
    routes = Path("app/routes.py").read_text()
    assert "interrupt(" in graph
    assert "create_ticket_for_user" in graph
    assert "create_ticket_for_user" in routes
    assert "create_ticket(" not in graph


def test_no_web_search_dependency_remains():
    all_files = [
        p for p in Path("app").rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    combined = "\n".join(p.read_text() for p in all_files)
    assert "TAVILY_API_KEY" not in combined
    assert "api.tavily.com" not in combined
    assert "search_web" not in combined


def test_ticket_lookup_has_deterministic_route():
    utils = Path("app/agents/utils.py").read_text()
    supervisor = Path("app/agents/supervisor.py").read_text()
    assert "def direct_route" in utils
    assert "direct_route(message)" in supervisor
    assert "deterministic_read_only_route" in supervisor


def test_conditional_ticket_request_is_not_unconditionally_actioned():
    utils = Path("app/agents/utils.py").read_text()
    assert "explicit_markers" in utils
    assert '"file a ticket"' in utils
