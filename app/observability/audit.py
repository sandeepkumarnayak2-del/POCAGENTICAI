from app.database.db import SessionLocal
from app.database.models import AuditLog
#resource as the type , approval,conversation
def audit(user_id, action, resource="", details=""):
    db = SessionLocal()
    try:
        db.add(AuditLog(user_id=user_id, action=action, resource=resource, details=details))
        db.commit()
    finally:
        db.close()
