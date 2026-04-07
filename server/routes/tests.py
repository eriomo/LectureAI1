import uuid
import json
from flask import Blueprint, request, jsonify
from db.supabase_client import supabase

bp = Blueprint("tests", __name__)


@bp.post("/create_test")
def create_test():
    try:
        d = request.json or {}
        tid = str(uuid.uuid4())
        supabase().table("tests").insert({
            "id": tid,
            "class_code": d.get("classCode", ""),
            "teacher_email": d.get("teacherEmail", ""),
            "title": d.get("title", ""),
            "questions": json.dumps(d.get("questions", [])),
            "time_limit": int(d.get("timeLimit", 0)),
        }).execute()
        return jsonify({"success": True, "id": tid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_tests")
def get_tests():
    try:
        d = request.json or {}
        code = d.get("classCode", "").upper().strip()
        result = supabase().table("tests").select("*") \
            .eq("class_code", code).order("created_at", desc=True).execute()
        rows = []
        for r in (result.data or []):
            r["questions"] = json.loads(r["questions"]) if isinstance(r["questions"], str) else r["questions"]
            rows.append(r)
        return jsonify({"success": True, "tests": rows})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/delete_test")
def delete_test():
    try:
        d = request.json or {}
        tid = d.get("id", "")
        sb = supabase()
        sb.table("test_submissions").delete().eq("test_id", tid).execute()
        sb.table("tests").delete().eq("id", tid).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/submit_test")
def submit_test():
    try:
        d = request.json or {}
        answers = d.get("answers", {})
        questions = d.get("questions", [])
        score = sum(
            1 for i, q in enumerate(questions)
            if str(i) in answers and int(answers[str(i)]) == int(q.get("ans", -1))
        )
        sb = supabase()
        existing = sb.table("test_submissions").select("id") \
            .eq("test_id", d.get("testId", "")) \
            .eq("student_email", d.get("studentEmail", "")).limit(1).execute()
        if existing.data:
            return jsonify({"success": False, "error": "Already submitted"})
        sb.table("test_submissions").insert({
            "id": str(uuid.uuid4()),
            "test_id": d.get("testId", ""),
            "class_code": d.get("classCode", ""),
            "student_email": d.get("studentEmail", ""),
            "student_name": d.get("studentName", ""),
            "answers": json.dumps(answers),
            "score": score,
            "total": len(questions),
        }).execute()
        return jsonify({"success": True, "score": score, "total": len(questions)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_test_results")
def get_test_results():
    try:
        d = request.json or {}
        result = supabase().table("test_submissions").select("*") \
            .eq("test_id", d.get("testId", "")) \
            .order("submitted_at", desc=True).execute()
        return jsonify({"success": True, "results": result.data or []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_my_test_result")
def get_my_test_result():
    try:
        d = request.json or {}
        result = supabase().table("test_submissions").select("*") \
            .eq("test_id", d.get("testId", "")) \
            .eq("student_email", d.get("studentEmail", "")).limit(1).execute()
        return jsonify({"success": True, "result": result.data[0] if result.data else None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
