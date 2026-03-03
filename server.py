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

def parse_note_sections(notes_text):
    sections = []
    # Match numbered sections in any case format: "1. Introduction" or "1. INTRODUCTION"
    pattern = re.compile(r'(?:^|\n)(\d+)\.\s+([A-Za-z][^\n]+)\n([\s\S]*?)(?=(?:\n\d+\.\s+[A-Za-z])|$)')
    matches = list(pattern.finditer('\n' + notes_text))
    for m in matches:
        title = m.group(2).strip()
        body = m.group(3).strip()
        lines = []
        for l in body.split('\n'):
            clean = re.sub(r'^[\s•\-\*\d\.]+', '', l).strip()
            if len(clean) > 15:
                lines.append(clean[:140])
            if len(lines) >= 6:
                break
        narration = body.replace('\n', ' ')[:600]
        sections.append({'title': title, 'bullets': lines, 'narration': narration, 'full': body[:800]})
    if not sections:
        paras = [p.strip() for p in notes_text.split('\n\n') if len(p.strip()) > 40]
        for i, para in enumerate(paras[:8]):
            ls = [re.sub(r'^[•\-\*\d\.\s]+', '', l).strip() for l in para.split('\n') if len(l.strip()) > 15]
            sections.append({'title': f'Section {i+1}', 'bullets': ls[:6], 'narration': para.replace('\n', ' ')[:500], 'full': para[:800]})
    return sections

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
        code = d.get("code","").upper().strip()
        if not code: return jsonify({"success": False, "error": "No code"})
        init_db(); conn = get_db()
        conn.execute("""INSERT INTO classes (code,teacher_email,teacher_name,topic,level,data)
            VALUES(?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET
            teacher_email=excluded.teacher_email,teacher_name=excluded.teacher_name,
            topic=excluded.topic,level=excluded.level,data=excluded.data""",
            (code,d.get("teacherEmail",""),d.get("teacherName",""),
             d.get("topic",""),d.get("level",""),json.dumps(d)))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_class", methods=["POST"])
def get_class():
    try:
        d = request.json
        code = d.get("code","").upper().strip()
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
            (aid,d.get("classCode",""),d.get("teacherEmail",""),d.get("title",""),
             d.get("description",""),d.get("dueDate",""),int(d.get("maxScore",100))))
        conn.commit(); conn.close()
        return jsonify({"success": True, "id": aid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_assignments", methods=["POST"])
def get_assignments():
    try:
        d = request.json; code = d.get("classCode","").upper().strip()
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM assignments WHERE class_code=? ORDER BY created_at DESC",(code,)).fetchall()
        conn.close()
        return jsonify({"success": True, "assignments": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/delete_assignment", methods=["POST"])
def delete_assignment():
    try:
        d = request.json; aid = d.get("id","")
        init_db(); conn = get_db()
        conn.execute("DELETE FROM assignments WHERE id=?",(aid,))
        conn.execute("DELETE FROM submissions WHERE assignment_id=?",(aid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/submit_assignment", methods=["POST"])
def submit_assignment():
    try:
        d = request.json; init_db(); conn = get_db()
        existing = conn.execute("SELECT id FROM submissions WHERE assignment_id=? AND student_email=?",
            (d.get("assignmentId",""),d.get("studentEmail",""))).fetchone()
        if existing:
            conn.execute("UPDATE submissions SET content=?,submitted_at=datetime('now') WHERE id=?",
                (d.get("content",""),existing["id"]))
        else:
            conn.execute("""INSERT INTO submissions
                (id,assignment_id,class_code,student_email,student_name,content,submitted_at)
                VALUES(?,?,?,?,?,?,datetime('now'))""",
                (str(uuid.uuid4()),d.get("assignmentId",""),d.get("classCode",""),
                 d.get("studentEmail",""),d.get("studentName",""),d.get("content","")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_submissions", methods=["POST"])
def get_submissions():
    try:
        d = request.json; aid = d.get("assignmentId","")
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM submissions WHERE assignment_id=? ORDER BY submitted_at DESC",(aid,)).fetchall()
        conn.close()
        return jsonify({"success": True, "submissions": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/grade_submission", methods=["POST"])
def grade_submission():
    try:
        d = request.json; init_db(); conn = get_db()
        conn.execute("UPDATE submissions SET score=?,feedback=? WHERE id=?",
            (int(d.get("score",0)),d.get("feedback",""),d.get("submissionId","")))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_my_submission", methods=["POST"])
def get_my_submission():
    try:
        d = request.json; init_db(); conn = get_db()
        row = conn.execute("SELECT * FROM submissions WHERE assignment_id=? AND student_email=?",
            (d.get("assignmentId",""),d.get("studentEmail",""))).fetchone()
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
            (tid,d.get("classCode",""),d.get("teacherEmail",""),d.get("title",""),
             json.dumps(d.get("questions",[])),int(d.get("timeLimit",0))))
        conn.commit(); conn.close()
        return jsonify({"success": True, "id": tid})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_tests", methods=["POST"])
def get_tests():
    try:
        d = request.json; code = d.get("classCode","").upper().strip()
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM tests WHERE class_code=? ORDER BY created_at DESC",(code,)).fetchall()
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
        conn.execute("DELETE FROM tests WHERE id=?",(tid,))
        conn.execute("DELETE FROM test_submissions WHERE test_id=?",(tid,))
        conn.commit(); conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/submit_test", methods=["POST"])
def submit_test():
    try:
        d = request.json
        answers = d.get("answers",{}); questions = d.get("questions",[])
        score = sum(1 for i,q in enumerate(questions)
                    if str(i) in answers and int(answers[str(i)])==int(q.get("ans",-1)))
        init_db(); conn = get_db()
        existing = conn.execute("SELECT id FROM test_submissions WHERE test_id=? AND student_email=?",
            (d.get("testId",""),d.get("studentEmail",""))).fetchone()
        if existing: return jsonify({"success": False, "error": "Already submitted"})
        conn.execute("""INSERT INTO test_submissions
            (id,test_id,class_code,student_email,student_name,answers,score,total,submitted_at)
            VALUES(?,?,?,?,?,?,?,?,datetime('now'))""",
            (str(uuid.uuid4()),d.get("testId",""),d.get("classCode",""),
             d.get("studentEmail",""),d.get("studentName",""),
             json.dumps(answers),score,len(questions)))
        conn.commit(); conn.close()
        return jsonify({"success": True, "score": score, "total": len(questions)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_test_results", methods=["POST"])
def get_test_results():
    try:
        d = request.json; tid = d.get("testId","")
        init_db(); conn = get_db()
        rows = conn.execute("SELECT * FROM test_submissions WHERE test_id=? ORDER BY submitted_at DESC",(tid,)).fetchall()
        conn.close()
        return jsonify({"success": True, "results": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/get_my_test_result", methods=["POST"])
def get_my_test_result():
    try:
        d = request.json; init_db(); conn = get_db()
        row = conn.execute("SELECT * FROM test_submissions WHERE test_id=? AND student_email=?",
            (d.get("testId",""),d.get("studentEmail",""))).fetchone()
        conn.close()
        return jsonify({"success": True, "result": dict(row) if row else None})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/generate_notes", methods=["POST"])
def generate_notes():
    try:
        d = request.json
        topic=d.get("topic",""); level=d.get("level","Intermediate")
        duration=d.get("duration",75); objectives=d.get("objectives","")
        style=d.get("style","Lecture-based")
        p = f"""You are a senior university lecturer writing detailed lecture notes for students.
Generate VERY COMPREHENSIVE and DETAILED lecture notes for a {duration}-minute {level}-level class on "{topic}" using a {style} approach.

Learning objectives:
{objectives}

Use EXACTLY this numbered structure. Write at least 3-5 full paragraphs per section. Do not be brief.

1. Introduction
Explain why this topic is important in the real world. Give 2-3 real industries or problems that use it. Explain what students will be able to do after this class. Write at least 300 words.

2. Key Concepts
Define every important term. Explain each concept fully. Use simple language first then build to technical language. Write at least 400 words.

3. Detailed Explanations
Go deep. Explain HOW things work step by step. Cover edge cases. Explain assumptions. Write at least 400 words.

4. Worked Examples
Give at least 3 fully worked examples with step-by-step solutions. Show all working. Explain each step. Write at least 400 words.

5. Common Misconceptions
List at least 5 things students commonly get wrong. Explain WHY they are wrong. Explain what the correct understanding is. Write at least 300 words.

6. Summary
Recap every major point. Write in bullet points. At least 10 bullets.

7. Further Reading
Suggest 5 specific books, papers, or topics to explore next. Explain why each one is valuable.

Write in clear academic English. Be thorough. Do not skip any section. These notes must be detailed enough for a student to pass an exam using them alone."""
        result = ask_groq(p, max_tokens=3500)
        code = d.get("classCode","").upper().strip()
        if code:
            init_db(); conn = get_db()
            row = conn.execute("SELECT data FROM classes WHERE code=?",(code,)).fetchone()
            if row:
                cls = json.loads(row["data"])
                cls["notes"] = result
                conn.execute("UPDATE classes SET data=? WHERE code=?",(json.dumps(cls),code))
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
        row = conn.execute("SELECT data FROM classes WHERE code=?",(code,)).fetchone()
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
        p = f'Instructor. Topic:"{d.get("topic")}". {d.get("total_duration")}min total. {d.get("mins_elapsed")}min elapsed. {rem}min remain. On:"{d.get("current_segment")}".\nAre they on track? What to do now? What to skip if needed?'
        return jsonify({"result": ask_groq(p)})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/layer2/student_question", methods=["POST"])
def layer2_student_question():
    try:
        d = request.json
        p = f'Friendly tutor. Topic:"{d.get("topic")}". Student:{d.get("name")}, {d.get("year")}, background:{d.get("background")}, level:{d.get("level")}.\nQuestion:"{d.get("question")}"\nAnswer in under 150 words using everyday language. Personalise to their background. End with encouragement using their name.'
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
        duration = d.get("duration",75); style = d.get("style","Lecture-based")
        objectives = d.get("objectives",""); notes = d.get("notes","")

        GREEN=RGBColor(0x2d,0x6a,0x4f); WHITE=RGBColor(0xFF,0xFF,0xFF)
        DARK=RGBColor(0x1a,0x1a,0x1a); LGRAY=RGBColor(0xF7,0xF5,0xF2)
        ACCENT=RGBColor(0x74,0xC6,0x9D); DKGREEN=RGBColor(0x1B,0x43,0x32)
        MIDGREEN=RGBColor(0x52,0x96,0x6B)

        prs = Presentation()
        prs.slide_width = Inches(13.33); prs.slide_height = Inches(7.5)
        blank = prs.slide_layouts[6]

        def rect(slide,l,t,w,h,c,alpha=None):
            s=slide.shapes.add_shape(1,Inches(l),Inches(t),Inches(w),Inches(h))
            s.fill.solid(); s.fill.fore_color.rgb=c; s.line.fill.background(); return s

        def addtxt(slide,text,l,t,w,h,sz=18,bold=False,color=None,align=PP_ALIGN.LEFT,wrap=True):
            tb=slide.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h))
            tf=tb.text_frame; tf.word_wrap=wrap; p=tf.paragraphs[0]; p.alignment=align
            run=p.add_run(); run.text=str(text); run.font.size=Pt(sz); run.font.bold=bold
            run.font.color.rgb=color if color else DARK

        def addtxt_multi(slide,lines,l,t,w,h,sz=16,color=None,bullet_color=None):
            tb=slide.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h))
            tf=tb.text_frame; tf.word_wrap=True
            for i,line in enumerate(lines):
                p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
                p.alignment=PP_ALIGN.LEFT
                run=p.add_run()
                run.text=("▸  " if bullet_color else "")+str(line)
                run.font.size=Pt(sz)
                run.font.color.rgb=color if color else DARK

        # ── TITLE SLIDE ──
        s1=prs.slides.add_slide(blank)
        rect(s1,0,0,13.33,7.5,GREEN)
        rect(s1,0,5.6,13.33,1.9,DKGREEN)
        rect(s1,0,0,0.25,7.5,ACCENT)
        addtxt(s1,"🎓 LectureAI",0.5,0.3,12,0.55,sz=14,color=ACCENT,align=PP_ALIGN.LEFT)
        addtxt(s1,topic,0.5,1.0,12.3,2.8,sz=44,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        addtxt(s1,level+" Level  |  "+str(duration)+" min  |  "+style,0.5,3.9,12.3,0.7,sz=18,color=ACCENT,align=PP_ALIGN.CENTER)
        src="Built from AI Lecture Notes" if notes else "LectureAI Lesson Plan"
        addtxt(s1,src,0.5,4.7,12.3,0.5,sz=13,color=RGBColor(0xB7,0xDF,0xC8),align=PP_ALIGN.CENTER)

        # ── OBJECTIVES SLIDE ──
        s2=prs.slides.add_slide(blank)
        s2.background.fill.solid(); s2.background.fill.fore_color.rgb=LGRAY
        rect(s2,0,0,13.33,1.4,GREEN); rect(s2,0,6.9,13.33,0.6,DKGREEN)
        rect(s2,0,0,0.18,7.5,ACCENT)
        addtxt(s2,"Learning Objectives",0.4,0.25,12,0.9,sz=30,bold=True,color=WHITE)
        obj_lines=[o.lstrip("0123456789. ").strip() for o in objectives.strip().split("\n") if o.strip()][:7]
        if not obj_lines: obj_lines=["Understand core concepts","Apply the methods","Evaluate results","Reflect on learning"]
        for i,obj in enumerate(obj_lines):
            y=1.6+i*0.75
            rect(s2,0.5,y+0.1,0.38,0.5,GREEN)
            addtxt(s2,str(i+1),0.5,y+0.12,0.38,0.46,sz=16,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
            addtxt(s2,obj,1.05,y+0.08,11.8,0.58,sz=16,color=DARK)

        if notes:
            sections = parse_note_sections(notes)
            for sec in sections:
                sl=prs.slides.add_slide(blank)
                sl.background.fill.solid(); sl.background.fill.fore_color.rgb=LGRAY
                rect(sl,0,0,13.33,1.45,GREEN); rect(sl,0,6.9,13.33,0.6,DKGREEN)
                rect(sl,0,0,0.18,7.5,ACCENT)
                title_txt=sec['title']
                addtxt(sl,title_txt,0.4,0.22,12.4,1.0,sz=28,bold=True,color=WHITE)
                bullets=sec.get('bullets',[])
                if not bullets and sec.get('full'):
                    raw=sec['full']
                    bullets=[l.strip() for l in raw.split('\n') if len(l.strip())>15][:6]
                y=1.65
                for b in bullets[:6]:
                    if y>6.6: break
                    rect(sl,0.4,y+0.1,0.2,0.38,ACCENT)
                    addtxt(sl,"▸",0.4,y+0.08,0.2,0.42,sz=14,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
                    lines=[]
                    words=b.split()
                    cur=""
                    for w in words:
                        if len(cur+" "+w)<80: cur=(cur+" "+w).strip()
                        else: lines.append(cur);cur=w
                    if cur: lines.append(cur)
                    for li,ln in enumerate(lines[:2]):
                        addtxt(sl,ln,0.75,y+0.06+li*0.38,12.1,0.42,sz=15,color=DARK)
                    y+=0.38*min(len(lines[:2]),2)+0.42
        else:
            segs=[("Introduction & Hook","Active",0.12,"Why it matters, real-world context, lesson goals"),
                  ("Core Concepts","Passive",0.35,"Key definitions, terminology, foundational theory"),
                  ("Guided Activity","Constructive",0.28,"Hands-on application, worked examples, peer explanation"),
                  ("Peer Discussion","Interactive",0.13,"Debate, defend reasoning, compare approaches"),
                  ("Wrap-Up","Constructive",0.12,"Summary, exit ticket, key takeaways")]
            icap_c={"Passive":RGBColor(0xC0,0x44,0x0A),"Active":RGBColor(0x1A,0x66,0x40),
                    "Constructive":RGBColor(0x1A,0x3F,0x80),"Interactive":RGBColor(0x6A,0x1A,0x80)}
            for i,(name,icap,pct,desc) in enumerate(segs):
                sl=prs.slides.add_slide(blank)
                sl.background.fill.solid(); sl.background.fill.fore_color.rgb=LGRAY
                rect(sl,0,0,13.33,1.45,GREEN); rect(sl,0,6.9,13.33,0.6,DKGREEN)
                rect(sl,0,0,0.18,7.5,ACCENT)
                addtxt(sl,"Segment "+str(i+1)+" of "+str(len(segs)),0.4,0.08,8,0.38,sz=12,color=ACCENT)
                addtxt(sl,name,0.4,0.38,9.5,0.9,sz=26,bold=True,color=WHITE)
                mins=max(5,round(duration*pct))
                rect(sl,10.8,0.22,2.3,1.0,DKGREEN)
                addtxt(sl,str(mins)+" min",10.8,0.38,2.3,0.65,sz=22,bold=True,color=ACCENT,align=PP_ALIGN.CENTER)
                ic=icap_c.get(icap,GREEN); rect(sl,0.4,1.65,2.2,0.5,ic)
                addtxt(sl,icap,0.4,1.68,2.2,0.44,sz=13,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
                addtxt(sl,desc,0.4,2.4,12.5,0.55,sz=16,bold=True,color=GREEN)
                addtxt(sl,"Topic: "+topic,0.4,3.1,12.5,0.55,sz=15,color=DARK)
                addtxt(sl,style+" delivery for "+level.lower()+"-level students",0.4,3.7,12.5,0.5,sz=14,color=RGBColor(0x55,0x55,0x55))

        # ── THANK YOU SLIDE ──
        sc=prs.slides.add_slide(blank)
        rect(sc,0,0,13.33,7.5,GREEN); rect(sc,0,5.3,13.33,2.2,DKGREEN)
        rect(sc,0,0,0.25,7.5,ACCENT)
        addtxt(sc,"Thank You",0.5,1.6,12.3,1.8,sz=56,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        addtxt(sc,"Questions about "+topic+"?",0.5,3.5,12.3,0.8,sz=24,color=ACCENT,align=PP_ALIGN.CENTER)
        addtxt(sc,"LectureAI · Human-AI Co-Orchestration",0.5,4.5,12.3,0.6,sz=14,color=RGBColor(0xB7,0xDF,0xC8),align=PP_ALIGN.CENTER)

        buf=io.BytesIO(); prs.save(buf); buf.seek(0)
        return send_file(buf,as_attachment=True,
            download_name="LectureAI_"+topic.replace(" ","_")+".pptx",
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
