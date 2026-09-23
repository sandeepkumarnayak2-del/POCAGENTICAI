from app.database.db import init_db
from app.tools.tickets import create_ticket, get_ticket

def test_ticket_idempotency():
    init_db()
    key = "test-idempotent-123"
    a = create_ticket("alice", "test", "demo", "low", key)
    b = create_ticket("alice", "test", "demo", "low", key)
    assert a.id == b.id

def test_ticket_exists():
    init_db()
    t = create_ticket("alice", "test2", "demo", "low", "test-idempotent-456")
    assert get_ticket(t.id, "alice", "employee").id == t.id
