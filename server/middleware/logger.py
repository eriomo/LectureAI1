import time
import json
from functools import wraps
from flask import request, g


def log_request(f):
    """Decorator: logs method, path, duration, status for every route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        start = time.time()
        g.start_time = start
        try:
            response = f(*args, **kwargs)
            status = response[1] if isinstance(response, tuple) else 200
        except Exception as exc:
            duration = round((time.time() - start) * 1000)
            print(json.dumps({
                "level": "ERROR",
                "method": request.method,
                "path": request.path,
                "duration_ms": duration,
                "error": str(exc),
            }))
            raise
        duration = round((time.time() - start) * 1000)
        data = request.get_json(silent=True) or {}
        print(json.dumps({
            "level": "INFO",
            "method": request.method,
            "path": request.path,
            "class_code": data.get("classCode", data.get("code", "")),
            "duration_ms": duration,
            "status": status,
        }))
        return response
    return decorated
