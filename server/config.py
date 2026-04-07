import os

# ── AI ──────────────────────────────────────────────────────────
GROQ_API_KEY      = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL        = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_MAX_TOKENS   = int(os.environ.get("GROQ_MAX_TOKENS", 4000))

# ── Supabase ────────────────────────────────────────────────────
SUPABASE_URL         = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SUPABASE_ANON_KEY    = os.environ.get("SUPABASE_ANON_KEY", "")

# ── App ─────────────────────────────────────────────────────────
PORT         = int(os.environ.get("PORT", 5000))
FLASK_ENV    = os.environ.get("FLASK_ENV", "production")
SECRET_KEY   = os.environ.get("SECRET_KEY", "change-me-in-production")

# ── Rate Limits ─────────────────────────────────────────────────
RATE_LIMIT_AI_MAX      = int(os.environ.get("RATE_LIMIT_AI_MAX", 10))
RATE_LIMIT_AI_WINDOW   = int(os.environ.get("RATE_LIMIT_AI_WINDOW", 60))

# ── AI Cache TTL ────────────────────────────────────────────────
AI_CACHE_TTL_HOURS = int(os.environ.get("AI_CACHE_TTL_HOURS", 24))

# ── Sendgrid / Email ────────────────────────────────────────────
SENDGRID_API_KEY  = os.environ.get("SENDGRID_API_KEY", "")
FROM_EMAIL        = os.environ.get("FROM_EMAIL", "noreply@lectureai.com")
