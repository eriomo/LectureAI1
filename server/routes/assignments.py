import uuid
from flask import Blueprint, request, jsonify
from db.supabase_client import supabase

bp = Blueprint("assignments", __name__)


@bp.post("/create_assignment")
def create_assignment():
    try:
        d = request.json or {}
        sb = supabase()
        aid = str(uuid.uuid4())
        sb.table("assignments").insert({
            "id": aid,
            "class_code": d.get("classCode", ""),
            "teacher_email": d.get("teacherEmail", ""),
            "title": d.get("title", ""),
            "description": d.get("description", ""),
            "due_date": d.get("dueDate") or None,
            "max_score": int(d.get("maxScore", 100)),
        }).execute()
        return jsonify({"success": True, "id": aid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_assignments")
def get_assignments():
    try:
        d = request.json or {}
        code = d.get("classCode", "").upper().strip()
        sb = supabase()
        result = sb.table("assignments").select("*") \
            .eq("class_code", code).order("created_at", desc=True).execute()
        return jsonify({"success": True, "assignments": result.data or []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/delete_assignment")
def delete_assignment():
    try:
        d = request.json or {}
        aid = d.get("id", "")
        sb = supabase()
        sb.table("submissions").delete().eq("assignment_id", aid).execute()
        sb.table("assignments").delete().eq("id", aid).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/submit_assignment")
def submit_assignment():
    try:
        d = request.json or {}
        sb = supabase()
        existing = sb.table("submissions").select("id") \
            .eq("assignment_id", d.get("assignmentId", "")) \
            .eq("student_email", d.get("studentEmail", "")).limit(1).execute()
        if existing.data:
            sb.table("submissions").update({"content": d.get("content", "")}) \
                .eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table("submissions").insert({
                "id": str(uuid.uuid4()),
                "assignment_id": d.get("assignmentId", ""),
                "class_code": d.get("classCode", ""),
                "student_email": d.get("studentEmail", ""),
                "student_name": d.get("studentName", ""),
                "content": d.get("content", ""),
                "score": -1,
                "feedback": "",
            }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_submissions")
def get_submissions():
    try:
        d = request.json or {}
        sb = supabase()
        result = sb.table("submissions").select("*") \
            .eq("assignment_id", d.get("assignmentId", "")) \
            .order("submitted_at", desc=True).execute()
        return jsonify({"success": True, "submissions": result.data or []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/grade_submission")
def grade_submission():
    try:
        d = request.json or {}
        sb = supabase()
        sb.table("submissions").update({
            "score": int(d.get("score", 0)),
            "feedback": d.get("feedback", ""),
        }).eq("id", d.get("submissionId", "")).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_my_submission")
def get_my_submission():
    try:
        d = request.json or {}
        sb = supabase()
        result = sb.table("submissions").select("*") \
            .eq("assignment_id", d.get("assignmentId", "")) \
            .eq("student_email", d.get("studentEmail", "")).limit(1).execute()
        return jsonify({"success": True, "submission": result.data[0] if result.data else None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/ai_feedback")
def ai_feedback_route():
    try:
        d = request.json or {}
        from services.ai_service import ai_feedback
        result = ai_feedback(d.get("title", ""), d.get("description", ""),
                             int(d.get("maxScore", 100)), d.get("content", ""))
        return jsonify({"success": True, "feedback": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
