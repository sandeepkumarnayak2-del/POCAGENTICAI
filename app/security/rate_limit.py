from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

# Use Redis/Key Value when configured; otherwise keep a local in-memory limiter
# so the project remains runnable with zero infrastructure.
#Redis used for mutiple instances rate limitor, in memory will go away
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    storage_uri=settings.rate_limit_storage_uri or None,
)
