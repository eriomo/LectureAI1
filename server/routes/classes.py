import json
from flask import Blueprint, request, jsonify
from db.supabase_client import supabase

bp = Blueprint("classes", __name__)


@bp.post("/save_class")
def save_class():
    try:
        d = request.json or {}
        code = d.get("code", "").upper().strip()
        if not code:
            return jsonify({"success": False, "error": "No code provided"})
        sb = supabase()
        sb.table("classes").upsert({
            "code": code,
            "teacher_email": d.get("teacherEmail", ""),
            "teacher_name": d.get("teacherName", ""),
            "topic": d.get("topic", ""),
            "level": d.get("level", ""),
            "data": json.dumps(d),
        }, on_conflict="code").execute()
        print(f"[classes] saved: {code}")
        return jsonify({"success": True, "code": code})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_class")
def get_class():
    try:
        d = request.json or {}
        code = d.get("code", "").upper().strip()
        if not code:
            return jsonify({"success": False, "error": "No code provided"})
        sb = supabase()
        result = sb.table("classes").select("data").eq("code", code).limit(1).execute()
        if result.data:
            return jsonify({"success": True, "class": json.loads(result.data[0]["data"])})
        return jsonify({"success": False, "error": "Code not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/save_notes")
def save_notes():
    """Store generated notes against a class code in Supabase."""
    try:
        d = request.json or {}
        code = d.get("classCode", "").upper().strip()
        notes = d.get("notes", "")
        if not code:
            return jsonify({"success": False, "error": "No code"})
        sb = supabase()
        # Fetch current data, inject notes, re-save
        result = sb.table("classes").select("data").eq("code", code).limit(1).execute()
        if result.data:
            cls = json.loads(result.data[0]["data"])
            cls["notes"] = notes
            sb.table("classes").update({"data": json.dumps(cls)}).eq("code", code).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/get_notes")
def get_notes():
    try:
        d = request.json or {}
        code = d.get("classCode", "").upper().strip()
        sb = supabase()
        result = sb.table("classes").select("data").eq("code", code).limit(1).execute()
        if result.data:
            cls = json.loads(result.data[0]["data"])
            return jsonify({"success": True, "notes": cls.get("notes", "")})
        return jsonify({"success": False, "error": "Class not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
