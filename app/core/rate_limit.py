from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


def get_forwarded_addr(request) -> str:
    """
    Resolve the real client IP for rate limiting behind a proxy (Nginx/Railway).

    Honors the first hop of X-Forwarded-For (set by the trusted edge proxy) and
    falls back to the direct socket address. Without this, every request appears
    to originate from the proxy's IP, so all users share one bucket (and one
    abuser can throttle everyone).

    Note: only trust X-Forwarded-For if your deployment terminates it at a
    proxy you control — otherwise a client can spoof this header.
    """
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        # "client, proxy1, proxy2" — the first entry is the original client
        return forwarded_for.split(",")[0].strip()
    return request.remote_addr or ""


# Shared rate limiter instance using the real client address
limiter = Limiter(key_func=get_forwarded_addr)

__all__ = ["limiter", "RateLimitExceeded", "_rate_limit_exceeded_handler"]
