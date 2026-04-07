import uuid
from flask import Blueprint, request, jsonify
from db.supabase_client import supabase

bp = Blueprint("social", __name__)

# ── DISCUSSIONS ─────────────────────────────────────────────────

@bp.post("/discussion/post")
def discussion_post():
    try:
        d = request.json or {}
        sb = supabase()
        did = str(uuid.uuid4())
        sb.table("discussions").insert({
            "id": did,
            "class_code": d.get("classCode", ""),
            "student_name": d.get("studentName", ""),
            "student_email": d.get("studentEmail", ""),
            "question": d.get("question", ""),
            "reply": "",
            "replied_by": "",
        }).execute()
        return jsonify({"success": True, "id": did})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/discussion/get")
def discussion_get():
    try:
        d = request.json or {}
        result = supabase().table("discussions").select("*") \
            .eq("class_code", d.get("classCode", "")) \
            .order("created_at", desc=True).execute()
        return jsonify({"success": True, "posts": result.data or []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/discussion/reply")
def discussion_reply():
    try:
        d = request.json or {}
        supabase().table("discussions").update({
            "reply": d.get("reply", ""),
            "replied_by": d.get("repliedBy", ""),
        }).eq("id", d.get("id", "")).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── REACTIONS ───────────────────────────────────────────────────

@bp.post("/save_reaction")
def save_reaction():
    try:
        d = request.json or {}
        sb = supabase()
        # Remove recent duplicate from same student
        sb.table("reactions").delete() \
            .eq("class_code", d.get("classCode", "")) \
            .eq("student_email", d.get("studentEmail", "")).execute()
        sb.table("reactions").insert({
            "id": str(uuid.uuid4()),
            "class_code": d.get("classCode", ""),
            "student_email": d.get("studentEmail", ""),
            "student_name": d.get("studentName", ""),
            "reaction": d.get("reaction", ""),
        }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_reactions")
def get_reactions():
    try:
        d = request.json or {}
        # Get reactions from last 5 minutes
        result = supabase().table("reactions").select("reaction") \
            .eq("class_code", d.get("classCode", "")).execute()
        counts: dict = {}
        for r in (result.data or []):
            counts[r["reaction"]] = counts.get(r["reaction"], 0) + 1
        return jsonify({"success": True, "reactions": counts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── CONFUSION HEATMAP ───────────────────────────────────────────

@bp.post("/save_confusion")
def save_confusion():
    try:
        d = request.json or {}
        supabase().table("confusion_events").insert({
            "id": str(uuid.uuid4()),
            "class_code": d.get("classCode", ""),
            "student_email": d.get("studentEmail", ""),
            "student_name": d.get("studentName", ""),
            "slide_index": int(d.get("slideIndex", 0)),
            "slide_title": d.get("slideTitle", ""),
        }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_confusion")
def get_confusion():
    try:
        d = request.json or {}
        result = supabase().table("confusion_events").select("*") \
            .eq("class_code", d.get("classCode", "")) \
            .order("created_at", desc=True).execute()
        return jsonify({"success": True, "events": result.data or []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── ATTENDANCE ──────────────────────────────────────────────────

@bp.post("/save_attendance")
def save_attendance():
    try:
        d = request.json or {}
        sb = supabase()
        existing = sb.table("attendance").select("id") \
            .eq("class_code", d.get("classCode", "")) \
            .eq("student_name", d.get("studentName", "")) \
            .eq("session_date", d.get("sessionDate", "")).limit(1).execute()
        present = 1 if d.get("present", True) else 0
        if existing.data:
            sb.table("attendance").update({"present": present}) \
                .eq("id", existing.data[0]["id"]).execute()
        else:
            sb.table("attendance").insert({
                "id": str(uuid.uuid4()),
                "class_code": d.get("classCode", ""),
                "teacher_email": d.get("teacherEmail", ""),
                "student_name": d.get("studentName", ""),
                "session_date": d.get("sessionDate", ""),
                "present": present,
            }).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_attendance")
def get_attendance():
    try:
        d = request.json or {}
        result = supabase().table("attendance").select("*") \
            .eq("class_code", d.get("classCode", "")) \
            .order("session_date", desc=True).execute()
        return jsonify({"success": True, "attendance": result.data or []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
