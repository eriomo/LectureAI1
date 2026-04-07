import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify
from db.supabase_client import supabase

bp = Blueprint("library", __name__)


@bp.post("/library/save")
def library_save():
    try:
        d = request.json or {}
        if not d.get("notes") or not d.get("topic"):
            return jsonify({"success": False, "error": "Topic and notes are required"})
        sb = supabase()
        year = str(datetime.now().year)
        existing = sb.table("lecture_library").select("id") \
            .eq("teacher_email", d.get("teacherEmail", "")) \
            .eq("topic", d.get("topic", "")).limit(1).execute()
        lid = existing.data[0]["id"] if existing.data else str(uuid.uuid4())
        payload = {
            "id": lid,
            "teacher_email": d.get("teacherEmail", ""),
            "teacher_name": d.get("teacherName", ""),
            "title": d.get("title", d.get("topic", "")),
            "topic": d.get("topic", ""),
            "subject": d.get("subject", ""),
            "level": d.get("level", "Intermediate"),
            "institution": d.get("institution", ""),
            "notes": d.get("notes", ""),
            "class_code": d.get("classCode", ""),
            "is_public": True if d.get("isPublic", True) else False,
            "year": year,
        }
        sb.table("lecture_library").upsert(payload, on_conflict="id").execute()
        return jsonify({"success": True, "id": lid, "updated": bool(existing.data)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/library/list")
def library_list():
    try:
        d = request.json or {}
        search = d.get("search", "").strip()
        level = d.get("level", "").strip()
        year = d.get("year", "").strip()
        teacher_email = d.get("teacherEmail", "").strip()
        page = int(d.get("page", 1))
        per_page = 20
        sb = supabase()
        q = sb.table("lecture_library").select(
            "id,teacher_name,teacher_email,title,topic,subject,level,institution,year,view_count,saved_at"
        ).eq("is_public", True)
        if level:
            q = q.eq("level", level)
        if year:
            q = q.eq("year", year)
        if teacher_email:
            q = q.eq("teacher_email", teacher_email)
        result = q.order("saved_at", desc=True).execute()
        rows = result.data or []
        if search:
            s = search.lower()
            rows = [r for r in rows if s in (r.get("topic","") + r.get("title","") + r.get("subject","") + r.get("teacher_name","")).lower()]
        total = len(rows)
        start = (page - 1) * per_page
        rows = rows[start:start + per_page]
        return jsonify({"success": True, "lectures": rows, "total": total, "page": page})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/library/get")
def library_get():
    try:
        d = request.json or {}
        lid = d.get("id", "")
        sb = supabase()
        result = sb.table("lecture_library").select("*").eq("id", lid).limit(1).execute()
        if result.data:
            sb.table("lecture_library").update({"view_count": result.data[0].get("view_count", 0) + 1}).eq("id", lid).execute()
            return jsonify({"success": True, "lecture": result.data[0]})
        return jsonify({"success": False, "error": "Not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@bp.post("/library/delete")
def library_delete():
    try:
        d = request.json or {}
        supabase().table("lecture_library").delete() \
            .eq("id", d.get("id", "")) \
            .eq("teacher_email", d.get("teacherEmail", "")).execute()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
