import os, re, json, io, sqlite3, uuid
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
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB init error:", e)

init_db()

def ask_groq(prompt):
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500, temperature=0.7)
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
        if not code:
            return jsonify({"success": False, "error": "No code"})
        init_db()
        conn = get_db()
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
        if not code:
            return jsonify({"success": False, "error": "No code"})
        init_db()
        conn = get_db()
        row = conn.execute("SELECT data FROM classes WHERE code=?", (code,)).fetchone()
        conn.close()
        if row:
            return jsonify({"success": True, "class": json.loads(row["data"])})
        return jsonify({"success": False, "error": "Code not found"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/create_assignment", methods=["POST"])
def create_assignment():
    try:
        d = request.json
        aid = str(uuid.uuid4())
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
        d = request.json
        code = d.get("classCode","").upper().strip()
        init_db(); conn = get_db()
        rows = conn.execute(
            "SELECT * FROM assignments WHERE class_code=? ORDER BY created_at DESC", (code,)).fetchall()
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
        d = request.json
        init_db(); conn = get_db()
        existing = conn.execute(
            "SELECT id FROM submissions WHERE assignment_id=? AND student_email=?",
            (d.get("assignmentId",""), d.get("studentEmail",""))).fetchone()
        if existing:
            conn.execute(
                "UPDATE submissions SET content=?,submitted_at=datetime('now') WHERE id=?",
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
        rows = conn.execute(
            "SELECT * FROM submissions WHERE assignment_id=? ORDER BY submitted_at DESC", (aid,)).fetchall()
        conn.close()
        return jsonify({"success": True, "submissions": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/grade_submission", methods=["POST"])
def grade_submission():
    try:
        d = request.json
        init_db(); conn = get_db()
        conn.execute("UPDATE submissions SET score=?,feedback=? WHERE id=?",
            (int(d.get("score",0)), d.get("feedback",""), d.get("submissionId","")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_my_submission", methods=["POST"])
def get_my_submission():
    try:
        d = request.json
        init_db(); conn = get_db()
        row = conn.execute(
            "SELECT * FROM submissions WHERE assignment_id=? AND student_email=?",
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
        d = request.json
        code = d.get("classCode","").upper().strip()
        init_db(); conn = get_db()
        rows = conn.execute(
            "SELECT * FROM tests WHERE class_code=? ORDER BY created_at DESC", (code,)).fetchall()
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
        existing = conn.execute(
            "SELECT id FROM test_submissions WHERE test_id=? AND student_email=?",
            (d.get("testId",""), d.get("studentEmail",""))).fetchone()
        if existing:
            return jsonify({"success": False, "error": "Already submitted"})
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
        rows = conn.execute(
            "SELECT * FROM test_submissions WHERE test_id=? ORDER BY submitted_at DESC", (tid,)).fetchall()
        conn.close()
        return jsonify({"success": True, "results": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_my_test_result", methods=["POST"])
def get_my_test_result():
    try:
        d = request.json
        init_db(); conn = get_db()
        row = conn.execute(
            "SELECT * FROM test_submissions WHERE test_id=? AND student_email=?",
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
        p = f"""You are an expert lecturer. Generate comprehensive, well-structured lecture notes for a {duration}-minute {level}-level class on "{topic}" using a {style} approach.

Learning objectives:
{objectives}

Write the notes with these sections:
1. INTRODUCTION - why this topic matters and real-world relevance
2. KEY CONCEPTS - explain each core idea clearly with definitions
3. DETAILED EXPLANATIONS - go deep on each concept with examples
4. WORKED EXAMPLES - at least 2 concrete step-by-step examples
5. COMMON MISCONCEPTIONS - what students get wrong and why
6. SUMMARY - bullet point recap of everything covered
7. FURTHER READING - 3 topics to explore next

Write in clear academic English. Be thorough. These are the full notes a student will study from."""
        result = ask_groq(p)
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
        d = request.json
        code = d.get("classCode","").upper().strip()
        if not code:
            return jsonify({"success": False, "error": "No code"})
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
        p = f'Instructor. Topic:"{d.get("topic")}" Level:{d.get("level")}. Confusion:"{d.get("confusion")}"\nGive a new analogy. Suggest a quick 3-minute rescue activity. End with one re-engage sentence.'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/layer2/conceptcheck", methods=["POST"])
def layer2_conceptcheck():
    try:
        d = request.json
        p = f'Instructor. Topic:"{d.get("topic")}" Level:{d.get("level")}. Asked:"{d.get("question")}". {d.get("correct_pct")}% correct.\nInterpret this result. What should the instructor do in the next 5 minutes?'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/layer2/pacing", methods=["POST"])
def layer2_pacing():
    try:
        d = request.json
        rem = int(d.get("total_duration",75)) - int(d.get("mins_elapsed",0))
        p = f'Instructor. Topic:"{d.get("topic")}". {d.get("total_duration")}min total. {d.get("mins_elapsed")}min elapsed. {rem}min remain. On:"{d.get("current_segment")}".\nAre they on track? What should they do now? What can they skip if needed?'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/layer2/student_question", methods=["POST"])
def layer2_student_question():
    try:
        d = request.json
        p = f'Friendly tutor. Topic:"{d.get("topic")}". Student: {d.get("name")}, {d.get("year")}, background:{d.get("background")}, level:{d.get("level")}.\nQuestion:"{d.get("question")}"\nAnswer in under 150 words using everyday language. Personalise to their background. End with encouragement using their name.'
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

@app.route("/generate_slides", methods=["POST"])
def generate_slides():
    try:
        d = request.json
        topic = d.get("topic","Topic"); level = d.get("level","Intermediate")
        duration = d.get("duration",75); objectives = d.get("objectives","")
        style = d.get("style","Lecture-based")
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
        s1=prs.slides.add_slide(blank)
        rect(s1,0,0,13.33,7.5,GREEN); rect(s1,0,5.8,13.33,1.7,DKGREEN)
        txt(s1,"LectureAI",0.5,0.4,12,0.6,sz=13,color=ACCENT,align=PP_ALIGN.CENTER)
        txt(s1,topic,0.5,1.2,12,2.2,sz=40,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        txt(s1,level+" | "+str(duration)+" min | "+style,0.5,3.6,12,0.7,sz=16,color=ACCENT,align=PP_ALIGN.CENTER)
        s2=prs.slides.add_slide(blank)
        s2.background.fill.solid(); s2.background.fill.fore_color.rgb=LGRAY
        rect(s2,0,0,13.33,1.2,GREEN)
        txt(s2,"Learning Objectives",0.4,0.2,12,0.85,sz=26,bold=True,color=WHITE)
        obj_lines=objectives.strip().split("\n") if objectives else ["Understand key concepts","Apply the methods","Evaluate results"]
        for i,obj in enumerate(obj_lines[:6]):
            y=1.5+i*0.85; rect(s2,0.5,y,0.4,0.55,GREEN)
            txt(s2,str(i+1),0.5,y+0.05,0.4,0.45,sz=15,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
            txt(s2,obj.lstrip("0123456789. "),1.1,y+0.08,11.7,0.5,sz=16,color=DARK)
        segs=[("Introduction and Hook","Active",0.12),("Core Concept","Passive",0.35),
              ("Guided Activity","Constructive",0.28),("Peer Discussion","Interactive",0.13),
              ("Wrap-Up","Constructive",0.12)]
        icap_c={"Passive":RGBColor(0xC0,0x44,0x0A),"Active":RGBColor(0x1A,0x66,0x40),
                "Constructive":RGBColor(0x1A,0x3F,0x80),"Interactive":RGBColor(0x6A,0x1A,0x80)}
        for i,(name,icap,pct) in enumerate(segs):
            s=prs.slides.add_slide(blank)
            s.background.fill.solid(); s.background.fill.fore_color.rgb=LGRAY
            rect(s,0,0,13.33,1.2,GREEN)
            txt(s,"Segment "+str(i+1),0.4,0.05,4,0.38,sz=11,color=ACCENT)
            txt(s,name,0.4,0.38,10,0.75,sz=24,bold=True,color=WHITE)
            mins=max(5,round(duration*pct))
            txt(s,str(mins)+" min",10.5,0.38,2.5,0.65,sz=19,bold=True,color=ACCENT,align=PP_ALIGN.RIGHT)
            ic=icap_c.get(icap,GREEN); rect(s,0.4,1.5,2.1,0.48,ic)
            txt(s,icap.upper(),0.4,1.52,2.1,0.44,sz=12,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
            txt(s,"Topic: "+topic,0.4,2.2,12.5,0.48,sz=17,bold=True,color=GREEN)
            txt(s,style+" for "+level.lower()+"-level students.",0.4,2.85,12.5,0.55,sz=15,color=DARK)
        sc=prs.slides.add_slide(blank)
        rect(sc,0,0,13.33,7.5,GREEN); rect(sc,0,5.5,13.33,2.0,DKGREEN)
        txt(sc,"Thank You",0.5,2.0,12,1.5,sz=52,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        txt(sc,"Questions about "+topic+"?",0.5,3.6,12,0.8,sz=22,color=ACCENT,align=PP_ALIGN.CENTER)
        buf=io.BytesIO(); prs.save(buf); buf.seek(0)
        return send_file(buf,as_attachment=True,
            download_name="LectureAI_"+topic.replace(" ","_")+".pptx",
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
