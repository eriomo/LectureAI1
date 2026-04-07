from collections import defaultdict
from functools import wraps
import time
from flask import request, jsonify
from config import RATE_LIMIT_AI_MAX, RATE_LIMIT_AI_WINDOW


class RateLimiter:
    def __init__(self):
        self.requests: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, identifier: str, max_requests: int = RATE_LIMIT_AI_MAX,
                   window_secs: int = RATE_LIMIT_AI_WINDOW) -> bool:
        now = time.time()
        self.requests[identifier] = [
            t for t in self.requests[identifier]
            if now - t < window_secs
        ]
        if len(self.requests[identifier]) >= max_requests:
            return False
        self.requests[identifier].append(now)
        return True

    def remaining(self, identifier: str, max_requests: int = RATE_LIMIT_AI_MAX,
                  window_secs: int = RATE_LIMIT_AI_WINDOW) -> int:
        now = time.time()
        recent = [t for t in self.requests[identifier] if now - t < window_secs]
        return max(0, max_requests - len(recent))


# Singleton
_limiter = RateLimiter()


def ai_rate_limit(f):
    """Decorator: apply rate limiting to AI endpoints by IP + class code."""
    @wraps(f)
    def decorated(*args, **kwargs):
        data = request.get_json(silent=True) or {}
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        code = data.get("classCode", "")
        identifier = f"{ip}:{code}"
        if not _limiter.is_allowed(identifier):
            return jsonify({
                "success": False,
                "error": f"Rate limit reached. Max {RATE_LIMIT_AI_MAX} AI requests per {RATE_LIMIT_AI_WINDOW}s. Please wait."
            }), 429
        return f(*args, **kwargs)
    return decorated
