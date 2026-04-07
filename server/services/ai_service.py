import json
import re
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, GROQ_MAX_TOKENS
from middleware.cache_middleware import get_cached, set_cache

_client: Groq | None = None


def _groq() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def ask(prompt: str, max_tokens: int = GROQ_MAX_TOKENS,
        temperature: float = 0.7) -> str:
    """Raw Groq call — returns text string."""
    r = _groq().chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return r.choices[0].message.content.strip()


def ask_cached(prompt_key: str, params: dict, prompt: str,
               max_tokens: int = GROQ_MAX_TOKENS) -> str:
    """Ask Groq but check/write Supabase cache first."""
    cached = get_cached(prompt_key, params)
    if cached:
        print(f"[ai_service] cache HIT: {prompt_key}/{params.get('topic')}")
        return cached
    result = ask(prompt, max_tokens=max_tokens)
    set_cache(prompt_key, params, result)
    return result


def parse_json_response(text: str) -> list | dict | None:
    """Safely extract JSON from an AI response that may have prose around it."""
    for attempt in [
        lambda: json.loads(text),
        lambda: json.loads(re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text).group()),
        lambda: json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())),
    ]:
        try:
            result = attempt()
            if result is not None:
                return result
        except Exception:
            pass
    return None


# ── High-level helpers used by routes ──────────────────────────

def generate_notes(topic, level, duration, objectives, style, language, class_code="") -> str:
    from prompts.notes_prompt import build_notes_prompt
    prompt = build_notes_prompt(topic, level, duration, objectives, style, language)
    return ask_cached("notes", {"topic": topic, "level": level, "language": language}, prompt, max_tokens=4000)


def generate_slideshow(topic, level, duration, notes, language) -> list:
    from prompts.slideshow_prompt import build_slideshow_prompt
    prompt = build_slideshow_prompt(topic, level, duration, notes, language)
    raw = ask(prompt, max_tokens=6000)
    slides = parse_json_response(raw)
    if slides and isinstance(slides, list) and len(slides) > 2:
        return slides
    return []


def generate_quiz(topic, level, notes, language) -> list:
    from prompts.quiz_prompt import build_quiz_prompt
    prompt = build_quiz_prompt(topic, level, notes, language)
    raw = ask_cached("quiz", {"topic": topic, "level": level, "language": language}, prompt, max_tokens=900)
    result = parse_json_response(raw)
    return result if isinstance(result, list) else []


def generate_adaptive_question(topic, level, previous_results, language) -> dict:
    from prompts.quiz_prompt import build_adaptive_quiz_prompt
    prompt = build_adaptive_quiz_prompt(topic, level, previous_results, language)
    raw = ask(prompt, max_tokens=400)
    result = parse_json_response(raw)
    return result if isinstance(result, dict) else {}


def generate_study_plan(topic, level, background, language) -> str:
    from prompts.live_tools_prompts import build_study_plan_prompt
    prompt = build_study_plan_prompt(topic, level, background, language)
    return ask(prompt, max_tokens=1500)


def ai_feedback(title, description, max_score, content) -> str:
    from prompts.live_tools_prompts import build_feedback_prompt
    return ask(build_feedback_prompt(title, description, max_score, content), max_tokens=300)


def live_question(topic, level, question) -> str:
    from prompts.live_tools_prompts import build_live_question_prompt
    return ask(build_live_question_prompt(topic, level, question))


def confusion_rescue(topic, level, confusion) -> str:
    from prompts.live_tools_prompts import build_confusion_rescue_prompt
    return ask(build_confusion_rescue_prompt(topic, level, confusion))


def pacing_check(topic, total, elapsed, segment) -> str:
    from prompts.live_tools_prompts import build_pacing_prompt
    return ask(build_pacing_prompt(topic, total, elapsed, segment))


def concept_check(topic, level, question, correct_pct) -> str:
    from prompts.live_tools_prompts import build_concept_check_prompt
    return ask(build_concept_check_prompt(topic, level, question, correct_pct))


def student_question(topic, level, name, year, background, question) -> str:
    from prompts.live_tools_prompts import build_student_question_prompt
    return ask(build_student_question_prompt(topic, level, name, year, background, question))


def video_script(topic, level) -> str:
    from prompts.live_tools_prompts import build_video_script_prompt
    return ask(build_video_script_prompt(topic, level), max_tokens=1200)


def rubric(task, rubric_type) -> str:
    from prompts.live_tools_prompts import build_rubric_prompt
    return ask(build_rubric_prompt(task, rubric_type))
