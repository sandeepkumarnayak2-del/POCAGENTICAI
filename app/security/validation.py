import re
from fastapi import HTTPException

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,50}$")

def validate_username(username: str) -> str:
    if not USERNAME_RE.fullmatch(username):
        raise HTTPException(400, "Invalid username")
    return username

def validate_message(message: str, max_len: int = 1000) -> str:
    if not message or not message.strip():
        raise HTTPException(400, "Message cannot be empty")
    if len(message) > max_len:
        raise HTTPException(413, f"Message exceeds {max_len} characters")
    return message.strip()

def sanitize_input(message: str) -> str:
    # Null char removal  and empty space 
    return message.replace("\x00", "").strip()
