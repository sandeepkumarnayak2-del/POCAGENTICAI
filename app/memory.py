"""Short/long-term memory helpers.

Short-term memory is owned by LangGraph checkpoints. Long-term memory is
durable, user-scoped application data stored in SQL.
"""
import re
from app.database.db import SessionLocal
from app.database.models import Memory

SECRET_PATTERNS = (
    "password", "api key", "apikey", "secret", "token", "bearer",
    "private key", "credential",
)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def recall_memories(username: str, query: str, limit: int = 5) -> list[dict]:
    q = _tokens(query)
    if not q:
        return []
    db = SessionLocal()
    try:
        rows = db.query(Memory).filter(Memory.username == username).order_by(
            Memory.importance.desc(), Memory.updated_at.desc()
        ).limit(100).all()
        scored = []
        for row in rows:
            overlap = len(q & _tokens(f"{row.memory_key} {row.value}"))
            if overlap:
                scored.append((overlap, row))
        scored.sort(key=lambda x: (x[0], x[1].importance), reverse=True)
        return [
            {"key": row.memory_key, "value": row.value, "importance": row.importance}
            for _, row in scored[:limit]
        ]
    finally:
        db.close()


def save_explicit_memory(username: str, message: str) -> dict | None:
    """Persist only explicit, non-secret user preferences/facts.

    Examples: 'remember that I use a MacBook' or 'I prefer email notifications'.
    """
    lower = message.lower()
    if not any(x in lower for x in ("remember that", "remember this", "i prefer", "my preference is")):
        return None
    if any(secret in lower for secret in SECRET_PATTERNS):
        return None

    patterns = [
        r"remember (?:that|this)\s+(.+)",
        r"i prefer\s+(.+)",
        r"my preference is\s+(.+)",
    ]
    value = next((m.group(1).strip() for p in patterns if (m := re.search(p, message, re.I))), None)
    if not value or len(value) > 500:
        return None

    key = "preference"
    db = SessionLocal()
    try:
        row = db.query(Memory).filter_by(username=username, memory_key=key).first()
        if row:
            row.value = value
            row.importance = 0.8
        else:
            row = Memory(username=username, memory_key=key, value=value, importance=0.8)
            db.add(row)
        db.commit()
        db.refresh(row)
        return {"key": row.memory_key, "value": row.value}
    finally:
        db.close()


def clear_user_memories(username: str) -> None:
    db = SessionLocal()
    try:
        db.query(Memory).filter(Memory.username == username).delete()
        db.commit()
    finally:
        db.close()
