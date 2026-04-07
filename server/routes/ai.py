from flask import Blueprint, request, jsonify, send_file
from middleware.rate_limiter import ai_rate_limit
import services.ai_service as ai

bp = Blueprint("ai", __name__)


@bp.post("/generate_notes")
@ai_rate_limit
def generate_notes():
    try:
        d = request.json or {}
        result = ai.generate_notes(
            topic=d.get("topic", ""),
            level=d.get("level", "Intermediate"),
            duration=d.get("duration", 75),
            objectives=d.get("objectives", ""),
            style=d.get("style", "Lecture-based"),
            language=d.get("language", "English"),
            class_code=d.get("classCode", ""),
        )
        # Also save notes to class record
        if d.get("classCode"):
            from routes.classes import _save_notes_to_class
            try:
                _save_notes_to_class(d["classCode"], result)
            except Exception:
                pass
        return jsonify({"success": True, "notes": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/generate_slideshow_data")
@ai_rate_limit
def generate_slideshow_data():
    try:
        d = request.json or {}
        slides = ai.generate_slideshow(
            topic=d.get("topic", ""),
            level=d.get("level", "Intermediate"),
            duration=d.get("duration", 75),
            notes=d.get("notes", ""),
            language=d.get("language", "English"),
        )
        if slides:
            return jsonify({"success": True, "slides": slides})
        return jsonify({"success": False, "error": "Could not parse slides — using local fallback"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/generate_quiz")
@ai_rate_limit
def generate_quiz():
    try:
        d = request.json or {}
        questions = ai.generate_quiz(
            topic=d.get("topic", ""),
            level=d.get("level", "Intermediate"),
            notes=d.get("notes", ""),
            language=d.get("language", "English"),
        )
        if questions:
            return jsonify({"success": True, "questions": questions})
        return jsonify({"success": False, "error": "Could not generate quiz"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/adaptive_quiz_question")
@ai_rate_limit
def adaptive_quiz_question():
    try:
        d = request.json or {}
        question = ai.generate_adaptive_question(
            topic=d.get("topic", ""),
            level=d.get("level", "Intermediate"),
            previous_results=d.get("previousResults", []),
            language=d.get("language", "English"),
        )
        return jsonify({"success": True, "question": question})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/generate_study_plan")
@ai_rate_limit
def generate_study_plan():
    try:
        d = request.json or {}
        result = ai.generate_study_plan(
            topic=d.get("topic", ""),
            level=d.get("level", "Intermediate"),
            background=d.get("background", ""),
            language=d.get("language", "English"),
        )
        return jsonify({"success": True, "plan": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/generate_video_script")
@ai_rate_limit
def generate_video_script():
    try:
        d = request.json or {}
        result = ai.video_script(d.get("topic", ""), d.get("level", "Intermediate"))
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)})


# ── Layer 2 real-time tools ─────────────────────────────────────

@bp.post("/layer2/question")
def layer2_question():
    try:
        d = request.json or {}
        return jsonify({"result": ai.live_question(d.get("topic",""), d.get("level",""), d.get("question",""))})
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.post("/layer2/confusion")
def layer2_confusion():
    try:
        d = request.json or {}
        return jsonify({"result": ai.confusion_rescue(d.get("topic",""), d.get("level",""), d.get("confusion",""))})
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.post("/layer2/pacing")
def layer2_pacing():
    try:
        d = request.json or {}
        return jsonify({"result": ai.pacing_check(d.get("topic",""), int(d.get("total_duration",75)), int(d.get("mins_elapsed",0)), d.get("current_segment",""))})
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.post("/layer2/conceptcheck")
def layer2_conceptcheck():
    try:
        d = request.json or {}
        return jsonify({"result": ai.concept_check(d.get("topic",""), d.get("level",""), d.get("question",""), int(d.get("correct_pct",0)))})
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.post("/layer2/student_question")
def layer2_student_question():
    try:
        d = request.json or {}
        return jsonify({"result": ai.student_question(d.get("topic",""), d.get("level",""), d.get("name",""), d.get("year",""), d.get("background",""), d.get("question",""))})
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.post("/layer2/rubric")
def layer2_rubric():
    try:
        d = request.json or {}
        return jsonify({"result": ai.rubric(d.get("task",""), d.get("type","Essay"))})
    except Exception as e:
        return jsonify({"error": str(e)})


@bp.post("/generate_slides")
def generate_slides():
    """PowerPoint export — imports pptx service."""
    try:
        from services.pptx_service import build_pptx
        d = request.json or {}
        buf = build_pptx(d)
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            as_attachment=True,
            download_name=f"LectureAI_{(d.get('topic','Lecture'))[:30].replace(' ','_')}.pptx",
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
