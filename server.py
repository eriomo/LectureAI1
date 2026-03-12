import os, json, io, sqlite3, uuid, re
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from groq import Groq
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

app = Flask(__name__, template_folder="templates")
CORS(app)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
DB_PATH = "/tmp/lectureai.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db()
        conn.execute("""CREATE TABLE IF NOT EXISTS classes (
            code TEXT PRIMARY KEY, teacher_email TEXT, teacher_name TEXT,
            topic TEXT, level TEXT, data TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS assignments (
            id TEXT PRIMARY KEY, class_code TEXT, teacher_email TEXT,
            title TEXT, description TEXT, due_date TEXT,
            max_score INTEGER DEFAULT 100, created_at TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS submissions (
            id TEXT PRIMARY KEY, assignment_id TEXT, class_code TEXT,
            student_email TEXT, student_name TEXT, content TEXT,
            submitted_at TEXT, score INTEGER DEFAULT -1, feedback TEXT DEFAULT '')""")
        conn.execute("""CREATE TABLE IF NOT EXISTS tests (
            id TEXT PRIMARY KEY, class_code TEXT, teacher_email TEXT,
            title TEXT, questions TEXT, time_limit INTEGER DEFAULT 0, created_at TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS test_submissions (
            id TEXT PRIMARY KEY, test_id TEXT, class_code TEXT,
            student_email TEXT, student_name TEXT, answers TEXT,
            score INTEGER DEFAULT 0, total INTEGER DEFAULT 0, submitted_at TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS attendance (
            id TEXT PRIMARY KEY, class_code TEXT, teacher_email TEXT,
            student_name TEXT, session_date TEXT,
            present INTEGER DEFAULT 1, created_at TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS discussions (
            id TEXT PRIMARY KEY, class_code TEXT, student_name TEXT,
            student_email TEXT, question TEXT, reply TEXT DEFAULT '',
            replied_by TEXT DEFAULT '', created_at TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS reactions (
            id TEXT PRIMARY KEY, class_code TEXT, student_email TEXT,
            student_name TEXT, reaction TEXT, created_at TEXT)""")
        conn.commit(); conn.close()
    except Exception as e:
        print("DB init error:", e)

init_db()

def ask_groq(prompt, max_tokens=1500):
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens, temperature=0.7)
    return r.choices[0].message.content.strip()

@app.route("/")
def index():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    return open(path, encoding="utf-8").read()

@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})

@app.route("/save_class", methods=["POST"])
def save_class():
    try:
        d = request.json
        code = d.get("code", "").upper().strip()
        if not code: return jsonify({"success": False, "error": "No code"})
        init_db(); conn = get_db()
        conn.execute("""INSERT INTO classes (code,teacher_email,teacher_name,topic,level,data)
            VALUES(?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET
            teacher_email=excluded.teacher_email, teacher_name=excluded.teacher_name,
            topic=excluded.topic, level=excluded.level, data=excluded.data""",
            (code, d.get("teacherEmail",""), d.get("teacherName",""),
             d.get("topic",""), d.get("level",""), json.dumps(d)))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_class", methods=["POST"])
def get_class():
    try:
        d = request.json
        code = d.get("code", "").upper().strip()
        if not code: return jsonify({"success": False, "error": "No code"})
        init_db(); conn = get_db()
        row = conn.execute("SELECT data FROM classes WHERE code=?", (code,)).fetchone()
        conn.close()
        if row: return jsonify({"success": True, "class": json.loads(row["data"])})
        return jsonify({"success": False, "error": "Code not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/create_assignment", methods=["POST"])
def create_assignment():
    try:
        d = request.json; aid = str(uuid.uuid4())
        init_db(); conn = get_db()
        conn.execute("""INSERT INTO assignments
            (id,class_code,teacher_email,title,description,due_date,max_score,created_at)
            VALUES(?,?,?,?,?,?,?,datetime('now'))""",
            (aid, d.get("classCode",""), d.get("teacherEmail",""), d.get("title",""),
             d.get("description",""), d.get("dueDate",""), int(d.get("maxScore",100))))
        conn.commit(); conn.close()
        return jsonify({"success": True, "id": aid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_assignments", methods=["POST"])
def get_assignments():
    try:
        d = request.json; code = d.get("classCode","").upper().strip()
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM assignments WHERE class_code=? ORDER BY created_at DESC", (code,)).fetchall()
        conn.close()
        return jsonify({"success": True, "assignments": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/delete_assignment", methods=["POST"])
def delete_assignment():
    try:
        d = request.json; aid = d.get("id","")
        init_db(); conn = get_db()
        conn.execute("DELETE FROM assignments WHERE id=?", (aid,))
        conn.execute("DELETE FROM submissions WHERE assignment_id=?", (aid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/submit_assignment", methods=["POST"])
def submit_assignment():
    try:
        d = request.json; init_db(); conn = get_db()
        existing = conn.execute("SELECT id FROM submissions WHERE assignment_id=? AND student_email=?",
            (d.get("assignmentId",""), d.get("studentEmail",""))).fetchone()
        if existing:
            conn.execute("UPDATE submissions SET content=?,submitted_at=datetime('now') WHERE id=?",
                (d.get("content",""), existing["id"]))
        else:
            conn.execute("""INSERT INTO submissions
                (id,assignment_id,class_code,student_email,student_name,content,submitted_at)
                VALUES(?,?,?,?,?,?,datetime('now'))""",
                (str(uuid.uuid4()), d.get("assignmentId",""), d.get("classCode",""),
                 d.get("studentEmail",""), d.get("studentName",""), d.get("content","")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_submissions", methods=["POST"])
def get_submissions():
    try:
        d = request.json; aid = d.get("assignmentId","")
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM submissions WHERE assignment_id=? ORDER BY submitted_at DESC", (aid,)).fetchall()
        conn.close()
        return jsonify({"success": True, "submissions": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/grade_submission", methods=["POST"])
def grade_submission():
    try:
        d = request.json; init_db(); conn = get_db()
        conn.execute("UPDATE submissions SET score=?,feedback=? WHERE id=?",
            (int(d.get("score",0)), d.get("feedback",""), d.get("submissionId","")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_my_submission", methods=["POST"])
def get_my_submission():
    try:
        d = request.json; init_db(); conn = get_db()
        row = conn.execute("SELECT * FROM submissions WHERE assignment_id=? AND student_email=?",
            (d.get("assignmentId",""), d.get("studentEmail",""))).fetchone()
        conn.close()
        return jsonify({"success": True, "submission": dict(row) if row else None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/create_test", methods=["POST"])
def create_test():
    try:
        d = request.json; tid = str(uuid.uuid4())
        init_db(); conn = get_db()
        conn.execute("""INSERT INTO tests
            (id,class_code,teacher_email,title,questions,time_limit,created_at)
            VALUES(?,?,?,?,?,?,datetime('now'))""",
            (tid, d.get("classCode",""), d.get("teacherEmail",""), d.get("title",""),
             json.dumps(d.get("questions",[])), int(d.get("timeLimit",0))))
        conn.commit(); conn.close()
        return jsonify({"success": True, "id": tid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_tests", methods=["POST"])
def get_tests():
    try:
        d = request.json; code = d.get("classCode","").upper().strip()
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM tests WHERE class_code=? ORDER BY created_at DESC", (code,)).fetchall()
        result = []
        for r in rows:
            rd = dict(r); rd["questions"] = json.loads(rd["questions"]); result.append(rd)
        conn.close()
        return jsonify({"success": True, "tests": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/delete_test", methods=["POST"])
def delete_test():
    try:
        d = request.json; tid = d.get("id","")
        init_db(); conn = get_db()
        conn.execute("DELETE FROM tests WHERE id=?", (tid,))
        conn.execute("DELETE FROM test_submissions WHERE test_id=?", (tid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/submit_test", methods=["POST"])
def submit_test():
    try:
        d = request.json
        answers = d.get("answers", {}); questions = d.get("questions", [])
        score = sum(1 for i, q in enumerate(questions)
                    if str(i) in answers and int(answers[str(i)]) == int(q.get("ans",-1)))
        init_db(); conn = get_db()
        existing = conn.execute("SELECT id FROM test_submissions WHERE test_id=? AND student_email=?",
            (d.get("testId",""), d.get("studentEmail",""))).fetchone()
        if existing: return jsonify({"success": False, "error": "Already submitted"})
        conn.execute("""INSERT INTO test_submissions
            (id,test_id,class_code,student_email,student_name,answers,score,total,submitted_at)
            VALUES(?,?,?,?,?,?,?,?,datetime('now'))""",
            (str(uuid.uuid4()), d.get("testId",""), d.get("classCode",""),
             d.get("studentEmail",""), d.get("studentName",""),
             json.dumps(answers), score, len(questions)))
        conn.commit(); conn.close()
        return jsonify({"success": True, "score": score, "total": len(questions)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_test_results", methods=["POST"])
def get_test_results():
    try:
        d = request.json; tid = d.get("testId","")
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM test_submissions WHERE test_id=? ORDER BY submitted_at DESC", (tid,)).fetchall()
        conn.close()
        return jsonify({"success": True, "results": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_my_test_result", methods=["POST"])
def get_my_test_result():
    try:
        d = request.json; init_db(); conn = get_db()
        row = conn.execute("SELECT * FROM test_submissions WHERE test_id=? AND student_email=?",
            (d.get("testId",""), d.get("studentEmail",""))).fetchone()
        conn.close()
        return jsonify({"success": True, "result": dict(row) if row else None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/generate_notes", methods=["POST"])
def generate_notes():
    try:
        d = request.json
        topic = d.get("topic",""); level = d.get("level","Intermediate")
        duration = d.get("duration",75); objectives = d.get("objectives","")
        style = d.get("style","Lecture-based")
        p = f"""You are an expert lecturer. Generate comprehensive lecture notes for a {duration}-minute {level}-level class on "{topic}" using a {style} approach.

Learning objectives:
{objectives}

Structure the notes with these exact sections:
1. INTRODUCTION
Why this topic matters and real-world relevance.

2. KEY CONCEPTS
Define and explain each core idea clearly.

3. DETAILED EXPLANATIONS
Go deep on each concept with examples and reasoning.

4. WORKED EXAMPLES
At least 2 concrete step-by-step examples.

5. COMMON MISCONCEPTIONS
What students often get wrong and why.

6. SUMMARY
Bullet point recap of everything covered.

7. FURTHER READING
3 topics to explore next.

Write in clear academic English. Be thorough. These are full notes a student will study from."""
        result = ask_groq(p, max_tokens=2000)
        code = d.get("classCode","").upper().strip()
        if code:
            init_db(); conn = get_db()
            row = conn.execute("SELECT data FROM classes WHERE code=?", (code,)).fetchone()
            if row:
                cls = json.loads(row["data"])
                cls["notes"] = result
                conn.execute("UPDATE classes SET data=? WHERE code=?", (json.dumps(cls), code))
                conn.commit()
            conn.close()
        return jsonify({"success": True, "notes": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_notes", methods=["POST"])
def get_notes():
    try:
        d = request.json; code = d.get("classCode","").upper().strip()
        if not code: return jsonify({"success": False, "error": "No code"})
        init_db(); conn = get_db()
        row = conn.execute("SELECT data FROM classes WHERE code=?", (code,)).fetchone()
        conn.close()
        if row:
            cls = json.loads(row["data"])
            return jsonify({"success": True, "notes": cls.get("notes","")})
        return jsonify({"success": False, "error": "Class not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/layer2/question", methods=["POST"])
def layer2_question():
    try:
        d = request.json
        p = f'Instructor. Topic:"{d.get("topic")}" Level:{d.get("level")}. Question:"{d.get("question")}"\nExplain clearly in 3 sentences. Note one common misconception. Give one follow-up question.'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/layer2/confusion", methods=["POST"])
def layer2_confusion():
    try:
        d = request.json
        p = f'Instructor. Topic:"{d.get("topic")}" Level:{d.get("level")}. Confusion:"{d.get("confusion")}"\nGive a new analogy. Suggest a 3-minute rescue activity. End with one re-engage sentence.'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/layer2/conceptcheck", methods=["POST"])
def layer2_conceptcheck():
    try:
        d = request.json
        p = f'Instructor. Topic:"{d.get("topic")}" Level:{d.get("level")}. Asked:"{d.get("question")}". {d.get("correct_pct")}% correct.\nInterpret this. What should the instructor do in the next 5 minutes?'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/layer2/pacing", methods=["POST"])
def layer2_pacing():
    try:
        d = request.json
        rem = int(d.get("total_duration",75)) - int(d.get("mins_elapsed",0))
        p = f'Instructor. Topic:"{d.get("topic")}". {d.get("total_duration")}min total. {d.get("mins_elapsed")}min elapsed. {rem}min remain. On:"{d.get("current_segment")}".\nAre they on track? What to do now? What can be skipped?'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/layer2/student_question", methods=["POST"])
def layer2_student_question():
    try:
        d = request.json
        p = f'Friendly tutor. Topic:"{d.get("topic")}". Student:{d.get("name")}, {d.get("year")}, background:{d.get("background")}, level:{d.get("level")}.\nQuestion:"{d.get("question")}"\nAnswer in under 150 words. Use everyday language. End with encouragement using their name.'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/generate_video_script", methods=["POST"])
def generate_video_script():
    try:
        d = request.json
        p = f'Write a 5-minute video lecture script for "{d.get("topic")}" at {d.get("level")} level. Include: hook intro, what it is, how it works, real example, common mistakes, summary outro. Use natural spoken language.'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

# ── NEW: AI feedback on assignment before grading ─────────────
@app.route("/ai_feedback", methods=["POST"])
def ai_feedback():
    try:
        d = request.json
        p = f"""You are a helpful academic assistant. A student submitted an assignment.

Assignment: {d.get("title","")}
Instructions: {d.get("description","")}
Max score: {d.get("maxScore",100)}
Student submission: {d.get("content","")}

Give concise, encouraging feedback in 3-4 sentences. Note one strength and one area to improve. Do not assign a score — that is the teacher's job."""
        result = ask_groq(p, max_tokens=300)
        return jsonify({"success": True, "feedback": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── NEW: AI quiz generator from lesson notes ──────────────────
@app.route("/generate_quiz", methods=["POST"])
def generate_quiz():
    try:
        d = request.json
        topic = d.get("topic",""); level = d.get("level","Intermediate")
        notes = d.get("notes","")
        context = f"Based on these lecture notes:\n{notes[:1200]}" if notes else f"Based on the topic: {topic}"
        p = f"""{context}

Create exactly 5 multiple choice questions for {level}-level students studying "{topic}".

Respond ONLY with valid JSON — no preamble, no markdown, just the array:
[
  {{"q": "Question text", "options": ["A text", "B text", "C text", "D text"], "ans": 0, "exp": "Brief explanation"}},
  ...
]

The "ans" field is the index (0-3) of the correct option."""
        result = ask_groq(p, max_tokens=900)
        match = re.search(r'\[.*\]', result, re.DOTALL)
        questions = json.loads(match.group() if match else result)
        return jsonify({"success": True, "questions": questions})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── NEW: Emoji reactions ──────────────────────────────────────
@app.route("/save_reaction", methods=["POST"])
def save_reaction():
    try:
        d = request.json
        init_db(); conn = get_db()
        conn.execute("""DELETE FROM reactions WHERE class_code=? AND student_email=?
            AND datetime(created_at) > datetime('now', '-30 seconds')""",
            (d.get("classCode",""), d.get("studentEmail","")))
        conn.execute("""INSERT INTO reactions (id,class_code,student_email,student_name,reaction,created_at)
            VALUES(?,?,?,?,?,datetime('now'))""",
            (str(uuid.uuid4()), d.get("classCode",""), d.get("studentEmail",""),
             d.get("studentName",""), d.get("reaction","")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_reactions", methods=["POST"])
def get_reactions():
    try:
        d = request.json; code = d.get("classCode","")
        init_db(); conn = get_db()
        rows = conn.execute("""SELECT reaction, COUNT(*) as cnt FROM reactions
            WHERE class_code=? AND datetime(created_at) > datetime('now', '-5 minutes')
            GROUP BY reaction""", (code,)).fetchall()
        conn.close()
        return jsonify({"success": True, "reactions": {r["reaction"]: r["cnt"] for r in rows}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── NEW: Attendance tracker ───────────────────────────────────
@app.route("/save_attendance", methods=["POST"])
def save_attendance():
    try:
        d = request.json
        init_db(); conn = get_db()
        existing = conn.execute("SELECT id FROM attendance WHERE class_code=? AND student_name=? AND session_date=?",
            (d.get("classCode",""), d.get("studentName",""), d.get("sessionDate",""))).fetchone()
        if existing:
            conn.execute("UPDATE attendance SET present=? WHERE id=?",
                (1 if d.get("present", True) else 0, existing["id"]))
        else:
            conn.execute("""INSERT INTO attendance (id,class_code,teacher_email,student_name,session_date,present,created_at)
                VALUES(?,?,?,?,?,?,datetime('now'))""",
                (str(uuid.uuid4()), d.get("classCode",""), d.get("teacherEmail",""),
                 d.get("studentName",""), d.get("sessionDate",""),
                 1 if d.get("present", True) else 0))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_attendance", methods=["POST"])
def get_attendance():
    try:
        d = request.json; code = d.get("classCode","")
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM attendance WHERE class_code=? ORDER BY session_date DESC, student_name", (code,)).fetchall()
        conn.close()
        return jsonify({"success": True, "attendance": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── NEW: Discussion board ─────────────────────────────────────
@app.route("/discussion/post", methods=["POST"])
def discussion_post():
    try:
        d = request.json; init_db(); conn = get_db()
        did = str(uuid.uuid4())
        conn.execute("""INSERT INTO discussions (id,class_code,student_name,student_email,question,created_at)
            VALUES(?,?,?,?,?,datetime('now'))""",
            (did, d.get("classCode",""), d.get("studentName",""), d.get("studentEmail",""), d.get("question","")))
        conn.commit(); conn.close()
        return jsonify({"success": True, "id": did})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/discussion/get", methods=["POST"])
def discussion_get():
    try:
        d = request.json; code = d.get("classCode","")
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM discussions WHERE class_code=? ORDER BY created_at DESC", (code,)).fetchall()
        conn.close()
        return jsonify({"success": True, "posts": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/discussion/reply", methods=["POST"])
def discussion_reply():
    try:
        d = request.json; init_db(); conn = get_db()
        conn.execute("UPDATE discussions SET reply=?, replied_by=? WHERE id=?",
            (d.get("reply",""), d.get("repliedBy",""), d.get("id","")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ── Slides (PowerPoint) ───────────────────────────────────────
@app.route("/generate_slides", methods=["POST"])
def generate_slides():
    try:
        d = request.json
        topic = d.get("topic","Topic"); level = d.get("level","Intermediate")
        duration = d.get("duration",75); objectives = d.get("objectives","")
        style = d.get("style","Lecture-based"); notes = d.get("notes","")
        GREEN = RGBColor(0x2d,0x6a,0x4f); WHITE = RGBColor(0xFF,0xFF,0xFF)
        DARK = RGBColor(0x1a,0x1a,0x1a); LGRAY = RGBColor(0xF7,0xF5,0xF2)
        ACCENT = RGBColor(0x74,0xC6,0x9D); DKGREEN = RGBColor(0x1B,0x43,0x32)
        prs = Presentation(); prs.slide_width=Inches(13.33); prs.slide_height=Inches(7.5)
        blank = prs.slide_layouts[6]
        def rect(slide,l,t,w,h,c):
            s=slide.shapes.add_shape(1,Inches(l),Inches(t),Inches(w),Inches(h))
            s.fill.solid(); s.fill.fore_color.rgb=c; s.line.fill.background(); return s
        def txt(slide,text,l,t,w,h,sz=18,bold=False,color=None,align=PP_ALIGN.LEFT):
            tb=slide.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h))
            tf=tb.text_frame; tf.word_wrap=True; p=tf.paragraphs[0]; p.alignment=align
            run=p.add_run(); run.text=text; run.font.size=Pt(sz); run.font.bold=bold
            run.font.color.rgb=color if color else DARK
        def add_content_slide(title_text, bullets, is_dark=False):
            s = prs.slides.add_slide(blank)
            bg = DKGREEN if is_dark else LGRAY
            rect(s,0,0,13.33,7.5,bg)
            rect(s,0,0,13.33,1.4,GREEN)
            txt(s,title_text,0.4,0.2,12.5,1.0,sz=28,bold=True,color=WHITE)
            txt(s,"LectureAI",11.5,0.22,1.5,0.5,sz=10,color=ACCENT)
            y=1.6
            for b in bullets[:6]:
                rect(s,0.4,y,0.05,0.35,ACCENT)
                txt(s,str(b),0.6,y,12.3,0.45,sz=16,color=WHITE if is_dark else DARK)
                y+=0.55
        # Title slide
        s1=prs.slides.add_slide(blank)
        rect(s1,0,0,13.33,7.5,GREEN); rect(s1,0,5.8,13.33,1.7,DKGREEN)
        txt(s1,"LectureAI",0.5,0.3,12,0.5,sz=13,color=ACCENT,align=PP_ALIGN.CENTER)
        txt(s1,topic,0.5,1.0,12,2.5,sz=40,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        txt(s1,level+" | "+str(duration)+" min | "+style,0.5,3.6,12,0.7,sz=16,color=ACCENT,align=PP_ALIGN.CENTER)
        txt(s1,"Human-AI Co-Orchestration in Education",0.5,6.0,12,0.6,sz=12,color=WHITE,align=PP_ALIGN.CENTER)
        if notes and len(notes) > 100:
            raw_headers = re.findall(r'\n(\d+\.\s+[A-Z][A-Z ]+)\n', notes)
            sections = re.split(r'\n\d+\.\s+[A-Z][A-Z ]+\n', notes)
            for i, header in enumerate(raw_headers[:6]):
                clean_header = re.sub(r'^\d+\.\s*','',header).strip()
                content = sections[i+1] if i+1 < len(sections) else ""
                lines = [re.sub(r'^[•\-\*\d\.]+\s*','',l).strip() for l in content.split('\n')]
                lines = [l for l in lines if len(l) > 8][:5]
                if not lines: lines = ["Key concepts and definitions","Important examples and applications","Core principles to understand"]
                add_content_slide(clean_header, lines, i%2==1)
        else:
            objs = [o.strip() for o in objectives.split('\n') if o.strip()][:5]
            for title_text, bullets, is_dark in [
                ("Learning Objectives", objs or ["Understand core concepts","Apply the methods","Evaluate your learning"], False),
                ("Why It Matters", [f"Real-world relevance of {topic}", f"Where {topic} is applied today","What problem it solves","Why students study this"], True),
                ("Core Concepts", [f"Fundamental principles of {topic}","Key terminology you need to know","How the parts connect","The logic behind the method"], False),
                ("Examples & Analogies", [f"Think of {topic} like sorting a drawer — rules first","A flowchart where each step depends on data","How it appears in a professional setting","Does the output match your intuition?"], True),
                ("Guided Activity", ["Apply what you just learned to a small problem","Work in pairs and talk through your reasoning","It is fine to be wrong — focus on thinking","Be ready to explain your approach"], False),
                ("Common Mistakes", ["Skipping the assumptions — always check them","Confusing correlation with causation","Over-complicating when simpler is better","Not validating results against common sense"], True),
                ("Summary", [f"Core idea: understand {topic} by applying it","Start with intuition before moving to formulas","Next: practise with a real example","Exit ticket: write one thing you learned today"], False),
            ]:
                add_content_slide(title_text, bullets, is_dark)
        sc = prs.slides.add_slide(blank)
        rect(sc,0,0,13.33,7.5,DKGREEN)
        txt(sc,"Thank You",0.5,1.5,12,1.5,sz=48,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        txt(sc,f"Questions about {topic}?",0.5,3.2,12,0.8,sz=22,color=ACCENT,align=PP_ALIGN.CENTER)
        txt(sc,"Built with LectureAI · Human-AI Co-Orchestration",0.5,6.5,12,0.6,sz=12,color=ACCENT,align=PP_ALIGN.CENTER)
        buf = io.BytesIO()
        prs.save(buf); buf.seek(0)
        return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                         as_attachment=True, download_name=f"LectureAI_{topic[:30].replace(' ','_')}.pptx")
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
