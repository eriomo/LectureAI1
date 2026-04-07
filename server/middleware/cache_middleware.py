import hashlib
import json
from datetime import datetime, timezone, timedelta
from db.supabase_client import supabase
from config import AI_CACHE_TTL_HOURS


def _cache_key(prompt_key: str, params: dict) -> str:
    raw = f"{prompt_key}:{params.get('topic','')}:{params.get('level','')}:{params.get('language','English')}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached(prompt_key: str, params: dict) -> str | None:
    """Return cached AI response or None."""
    try:
        key = _cache_key(prompt_key, params)
        sb = supabase()
        result = sb.table("ai_cache") \
            .select("response") \
            .eq("cache_key", key) \
            .gt("expires_at", datetime.now(timezone.utc).isoformat()) \
            .limit(1) \
            .execute()
        if result.data:
            return result.data[0]["response"]
    except Exception as e:
        print(f"[cache] get error: {e}")
    return None


def set_cache(prompt_key: str, params: dict, response: str,
              ttl_hours: int = AI_CACHE_TTL_HOURS) -> None:
    """Store an AI response in Supabase cache."""
    try:
        key = _cache_key(prompt_key, params)
        expires = (datetime.now(timezone.utc) + timedelta(hours=ttl_hours)).isoformat()
        sb = supabase()
        sb.table("ai_cache").upsert({
            "cache_key": key,
            "prompt_key": prompt_key,
            "topic": params.get("topic", ""),
            "level": params.get("level", ""),
            "language": params.get("language", "English"),
            "response": response,
            "expires_at": expires,
        }).execute()
    except Exception as e:
        print(f"[cache] set error: {e}")
