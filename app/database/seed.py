from pwdlib import PasswordHash

from app.database.db import SessionLocal
from app.database.models import User


password_hash = PasswordHash.recommended()


def seed():
    db = SessionLocal()

    users = [
    ("sandeep", "sandeep123", "user"),
    ("smarajit", "smarajit123", "user"),
    ("alice", "alice123", "user"),
    ("bob", "bob123", "user"),
    ("agent", "agent123", "agent"),
    ("admin", "admin123", "admin"),
]

    try:
        for username, password, role in users:
            existing = db.query(User).filter_by(username=username).first()

            if existing:
                continue

            db.add(
                User(
                    username=username,
                    password_hash=password_hash.hash(password),
                    role=role,
                )
            )

        db.commit()
    finally:
        db.close()
