import json, uuid
from app.database.db import SessionLocal
from app.database.models import Ticket
from app.observability.metrics import TOOL_CALLS

def list_tickets(username, role):
    db = SessionLocal()
    try:
        q = db.query(Ticket)
        if role not in ("helpdesk", "admin"):
            q = q.filter(Ticket.owner_username == username)
        return q.order_by(Ticket.id.desc()).all()
    finally:
        db.close()

def get_ticket(ticket_id, username, role):
    db = SessionLocal()
    try:
        t = db.get(Ticket, ticket_id)
        if not t:
            return None
        if role not in ("helpdesk", "admin") and t.owner_username != username:
            return "FORBIDDEN"
        return t
    finally:
        db.close()

#idempotency_key- used for uniue identifier of request, else multiple request will be created
def create_ticket(username, title, description, priority, idempotency_key=None):
    db = SessionLocal()
    try:
        if idempotency_key:
            old = db.query(Ticket).filter_by(idempotency_key=idempotency_key).first()
            if old:
                return old
        t = Ticket(owner_username=username, title=title, description=description,
                   priority=priority, idempotency_key=idempotency_key)
        db.add(t); db.commit(); db.refresh(t)
        TOOL_CALLS.labels("create_ticket", "success").inc()
        return t
    except Exception:
        TOOL_CALLS.labels("create_ticket", "error").inc()
        db.rollback()
        raise
    finally:
        db.close()

def serialize(t):
    return {"id": t.id, "owner": t.owner_username, "title": t.title,
            "description": t.description, "priority": t.priority, "status": t.status}
