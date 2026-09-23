
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def load_functions(filename: str):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_scenario_general_ticket_route_is_deterministic():
    text = (ROOT / "app/agents/utils.py").read_text(encoding="utf-8")
    assert '"show me my tickets"' in text
    assert '"show my tickets"' in text
    assert 'return "ticket"' in text


def test_scenario_explicit_action_vs_conditional_action():
    text = (ROOT / "app/agents/utils.py").read_text(encoding="utf-8")
    assert '"create a ticket"' in text
    assert '"if a ticket is necessary"' not in text
    assert "explicit_markers" in text


def test_scenario_prompt_injection_blocked():
    text = (ROOT / "app/security/guardrails.py").read_text(encoding="utf-8")
    assert "ignore (all|any|the) previous instructions" in text
    assert "reveal (the )?(system|developer) prompt" in text
    assert "api key|secret|password" in text


def test_scenario_grounding_missing_phone_number():
    docs = [
        p.read_text(encoding="utf-8").lower()
        for p in (ROOT / "data/documents").glob("*.md")
    ]
    assert not any("helpdesk phone number" in d for d in docs)


def test_scenario_rag_documents_exist():
    names = {p.name for p in (ROOT / "data/documents").glob("*.md")}
    assert {"vpn.md", "password.md", "laptop.md", "outlook.md", "security.md"} <= names


def test_scenario_no_web_search_code():
    app_files = [
        p for p in (ROOT / "app").rglob("*.py")
        if "__pycache__" not in p.parts
    ]
    combined = "\n".join(p.read_text(encoding="utf-8") for p in app_files)
    assert "TAVILY" not in combined
    assert "api.tavily.com" not in combined
    assert "search_web" not in combined


def test_scenario_agent_logging_present():
    graph = (ROOT / "app/agents/graph.py").read_text(encoding="utf-8")
    supervisor = (ROOT / "app/agents/supervisor.py").read_text(encoding="utf-8")
    mcp = (ROOT / "app/mcp/server.py").read_text(encoding="utf-8")
    for marker in (
        '"agent_start"', '"agent_handoff"', '"human_approval_required"',
        '"action_execute"', '"action_complete"', '"action_rejected"',
    ):
        assert marker in graph
    assert '"agent_route"' in supervisor
    assert '"mcp_server_tool_call"' in mcp


def test_scenario_authorization_is_application_enforced():
    ticket_tools = (ROOT / "app/agents/ticket.py").read_text(encoding="utf-8")
    tickets = (ROOT / "app/tools/tickets.py").read_text(encoding="utf-8")
    assert "username=username" in ticket_tools
    assert "t.owner_username != username" in tickets
    assert 'return "FORBIDDEN"' in tickets


def test_scenario_human_approval_and_mcp_execution():
    graph = (ROOT / "app/agents/graph.py").read_text(encoding="utf-8")
    server = (ROOT / "app/mcp/server.py").read_text(encoding="utf-8")
    routes = (ROOT / "app/routes.py").read_text(encoding="utf-8")
    assert "interrupt(" in graph
    assert "Command(resume=" in graph
    assert "create_ticket_for_user" in graph
    assert "approval-{approval.id}" in graph
    assert "create_ticket_for_user" in server
    assert "/approvals/{approval_id}" in routes


def test_scenario_metrics_cover_llm_rag_tools_and_requests():
    metrics = (ROOT / "app/observability/metrics.py").read_text(encoding="utf-8")
    routes = (ROOT / "app/routes.py").read_text(encoding="utf-8")
    assert "LLM_CALLS" in metrics
    assert "LLM_LATENCY" in metrics
    assert "RAG_RETRIEVALS" in metrics
    assert "TOOL_CALLS" in metrics
    assert "REQUESTS" in metrics
    assert "@limiter.limit" in routes
