import os
import re
import json
import io
import sqlite3
import uuid
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
        print("DB init error: " + str(e))

init_db()

def ask_groq(prompt, max_tokens=1500):
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        max_tokens=max_tokens, temperature=0.7)
    return r.choices[0].message.content

def ask_groq_text(prompt):
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        max_tokens=600, temperature=0.7)
    return r.choices[0].message.content.strip()

def clean_json(raw):
    raw = re.sub(r"```json\s*","",raw)
    raw = re.sub(r"```\s*","",raw)
    m = re.search(r"\{.*\}",raw,re.DOTALL)
    if m: raw = m.group(0)
    raw = re.sub(r'\\(?!["\\/bfnrtu])',r'\\\\',raw)
    return raw.strip()

@app.route("/")
def index():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),"templates","index.html")
    return open(path).read()

@app.route("/ping")
def ping():
    try:
        conn = get_db()
        rows = conn.execute("SELECT code,teacher_name,topic FROM classes").fetchall()
        conn.close()
        return jsonify({"status":"ok","saved_classes":[{"code":r["code"],"teacher":r["teacher_name"],"topic":r["topic"]} for r in rows]})
    except Exception as e:
        return jsonify({"status":"error","message":str(e)})

@app.route("/save_class",methods=["POST"])
def save_class():
    try:
        d = request.json
        code = d.get("code","").upper().strip()
        if not code: return jsonify({"success":False,"error":"No code"})
        init_db()
        conn = get_db()
        conn.execute("""INSERT INTO classes (code,teacher_email,teacher_name,topic,level,data)
            VALUES(?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET
            teacher_email=excluded.teacher_email, teacher_name=excluded.teacher_name,
            topic=excluded.topic, level=excluded.level, data=excluded.data""",
            (code,d.get("teacherEmail",""),d.get("teacherName",""),d.get("topic",""),d.get("level",""),json.dumps(d)))
        conn.commit(); conn.close()
        return jsonify({"success":True,"saved_code":code})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/get_class",methods=["POST"])
def get_class():
    try:
        d = request.json
        code = d.get("code","").upper().strip()
        if not code: return jsonify({"success":False,"error":"No code"})
        init_db()
        conn = get_db()
        row = conn.execute("SELECT data FROM classes WHERE code=?",(code,)).fetchone()
        conn.close()
        if row: return jsonify({"success":True,"class":json.loads(row["data"])})
        return jsonify({"success":False,"error":"Code not found: "+code})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/create_assignment",methods=["POST"])
def create_assignment():
    try:
        d = request.json
        aid = str(uuid.uuid4())
        init_db()
        conn = get_db()
        conn.execute("""INSERT INTO assignments (id,class_code,teacher_email,title,description,due_date,max_score,created_at)
            VALUES(?,?,?,?,?,?,?,datetime('now'))""",
            (aid,d.get("classCode",""),d.get("teacherEmail",""),d.get("title",""),
             d.get("description",""),d.get("dueDate",""),int(d.get("maxScore",100))))
        conn.commit(); conn.close()
        return jsonify({"success":True,"id":aid})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/get_assignments",methods=["POST"])
def get_assignments():
    try:
        d = request.json
        code = d.get("classCode","").upper().strip()
        init_db()
        conn = get_db()
        rows = conn.execute("SELECT * FROM assignments WHERE class_code=? ORDER BY created_at DESC",(code,)).fetchall()
        conn.close()
        return jsonify({"success":True,"assignments":[dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/delete_assignment",methods=["POST"])
def delete_assignment():
    try:
        d = request.json; aid = d.get("id","")
        init_db()
        conn = get_db()
        conn.execute("DELETE FROM assignments WHERE id=?",(aid,))
        conn.execute("DELETE FROM submissions WHERE assignment_id=?",(aid,))
        conn.commit(); conn.close()
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/submit_assignment",methods=["POST"])
def submit_assignment():
    try:
        d = request.json; sid = str(uuid.uuid4())
        init_db()
        conn = get_db()
        existing = conn.execute("SELECT id FROM submissions WHERE assignment_id=? AND student_email=?",
            (d.get("assignmentId",""),d.get("studentEmail",""))).fetchone()
        if existing:
            conn.execute("UPDATE submissions SET content=?,submitted_at=datetime('now') WHERE id=?",
                (d.get("content",""),existing["id"]))
        else:
            conn.execute("""INSERT INTO submissions (id,assignment_id,class_code,student_email,student_name,content,submitted_at)
                VALUES(?,?,?,?,?,?,datetime('now'))""",
                (sid,d.get("assignmentId",""),d.get("classCode",""),
                 d.get("studentEmail",""),d.get("studentName",""),d.get("content","")))
        conn.commit(); conn.close()
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/get_submissions",methods=["POST"])
def get_submissions():
    try:
        d = request.json; aid = d.get("assignmentId","")
        init_db()
        conn = get_db()
        rows = conn.execute("SELECT * FROM submissions WHERE assignment_id=? ORDER BY submitted_at DESC",(aid,)).fetchall()
        conn.close()
        return jsonify({"success":True,"submissions":[dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/grade_submission",methods=["POST"])
def grade_submission():
    try:
        d = request.json
        init_db()
        conn = get_db()
        conn.execute("UPDATE submissions SET score=?,feedback=? WHERE id=?",
            (int(d.get("score",0)),d.get("feedback",""),d.get("submissionId","")))
        conn.commit(); conn.close()
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/get_my_submission",methods=["POST"])
def get_my_submission():
    try:
        d = request.json
        init_db()
        conn = get_db()
        row = conn.execute("SELECT * FROM submissions WHERE assignment_id=? AND student_email=?",
            (d.get("assignmentId",""),d.get("studentEmail",""))).fetchone()
        conn.close()
        if row: return jsonify({"success":True,"submission":dict(row)})
        return jsonify({"success":True,"submission":None})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/create_test",methods=["POST"])
def create_test():
    try:
        d = request.json; tid = str(uuid.uuid4())
        init_db()
        conn = get_db()
        conn.execute("""INSERT INTO tests (id,class_code,teacher_email,title,questions,time_limit,created_at)
            VALUES(?,?,?,?,?,?,datetime('now'))""",
            (tid,d.get("classCode",""),d.get("teacherEmail",""),d.get("title",""),
             json.dumps(d.get("questions",[])),int(d.get("timeLimit",0))))
        conn.commit(); conn.close()
        return jsonify({"success":True,"id":tid})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/get_tests",methods=["POST"])
def get_tests():
    try:
        d = request.json
        code = d.get("classCode","").upper().strip()
        init_db()
        conn = get_db()
        rows = conn.execute("SELECT * FROM tests WHERE class_code=? ORDER BY created_at DESC",(code,)).fetchall()
        result = []
        for r in rows:
            rd = dict(r); rd["questions"] = json.loads(rd["questions"]); result.append(rd)
        conn.close()
        return jsonify({"success":True,"tests":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/delete_test",methods=["POST"])
def delete_test():
    try:
        d = request.json; tid = d.get("id","")
        init_db()
        conn = get_db()
        conn.execute("DELETE FROM tests WHERE id=?",(tid,))
        conn.execute("DELETE FROM test_submissions WHERE test_id=?",(tid,))
        conn.commit(); conn.close()
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/submit_test",methods=["POST"])
def submit_test():
    try:
        d = request.json
        answers = d.get("answers",{}); questions = d.get("questions",[])
        score = sum(1 for i,q in enumerate(questions) if str(i) in answers and int(answers[str(i)])==int(q.get("ans",-1)))
        sid = str(uuid.uuid4())
        init_db()
        conn = get_db()
        existing = conn.execute("SELECT id FROM test_submissions WHERE test_id=? AND student_email=?",
            (d.get("testId",""),d.get("studentEmail",""))).fetchone()
        if existing:
            return jsonify({"success":False,"error":"Already submitted"})
        conn.execute("""INSERT INTO test_submissions (id,test_id,class_code,student_email,student_name,answers,score,total,submitted_at)
            VALUES(?,?,?,?,?,?,?,?,datetime('now'))""",
            (sid,d.get("testId",""),d.get("classCode",""),d.get("studentEmail",""),
             d.get("studentName",""),json.dumps(answers),score,len(questions)))
        conn.commit(); conn.close()
        return jsonify({"success":True,"score":score,"total":len(questions)})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/get_test_results",methods=["POST"])
def get_test_results():
    try:
        d = request.json; tid = d.get("testId","")
        init_db()
        conn = get_db()
        rows = conn.execute("SELECT * FROM test_submissions WHERE test_id=? ORDER BY submitted_at DESC",(tid,)).fetchall()
        conn.close()
        return jsonify({"success":True,"results":[dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/get_my_test_result",methods=["POST"])
def get_my_test_result():
    try:
        d = request.json
        init_db()
        conn = get_db()
        row = conn.execute("SELECT * FROM test_submissions WHERE test_id=? AND student_email=?",
            (d.get("testId",""),d.get("studentEmail",""))).fetchone()
        conn.close()
        if row: return jsonify({"success":True,"result":dict(row)})
        return jsonify({"success":True,"result":None})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)})

@app.route("/generate",methods=["POST"])
def generate():
    d = request.json
    topic=d.get("topic",""); objectives=d.get("objectives","")
    level=d.get("level","Intermediate"); duration=d.get("duration",75); style=d.get("style","Lecture-based")
    prompt = f"""Expert instructional designer. Generate a lesson plan as JSON only. No markdown.
Topic:{topic} Level:{level} Duration:{duration}min Style:{style} Objectives:{objectives}
Return EXACTLY:
{{"outline":[{{"segment":"...","icap":"Passive|Active|Constructive|Interactive","duration_mins":0,"description":"..."}}],
"analogies":["...","...","..."],
"activities":[{{"title":"...","icap":"...","prompt":"..."}}],
"reflections":["...","...","...","..."],
"micro_explanation":"...",
"practice_questions":[{{"difficulty":"Easy|Medium|Hard","question":"...","hint":"..."}}],
"srl_prompts":["...","...","...","..."]}}"""
    try:
        raw = ask_groq(prompt,max_tokens=2000)
        result = json.loads(clean_json(raw))
        return jsonify({"success":True,"data":result})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}),500

@app.route("/generate_slide_content",methods=["POST"])
def generate_slide_content():
    d = request.json
    topic=d.get("topic",""); level=d.get("level",""); objectives=d.get("objectives",""); style=d.get("style","")
    prompt = f"""Expert educator creating slide content for "{topic}" ({level} level, {style} style).
Return ONLY JSON, no markdown:
{{"slides":[
  {{"title":"...","bullets":["...","...","..."],"speakerNote":"Natural spoken sentence for this slide, 2-3 sentences"}},
  ...
]}}
Generate exactly 8 slides: 1)Title, 2)Learning Objectives, 3)Introduction & Hook, 4)Core Concepts, 5)Key Examples, 6)Activity, 7)Common Mistakes, 8)Summary & Next Steps.
Make speakerNotes conversational — they will be read aloud by a voice assistant.
Topic={topic}, Objectives={objectives}"""
    try:
        raw = ask_groq(prompt,max_tokens=2500)
        result = json.loads(clean_json(raw))
        return jsonify({"success":True,"slides":result.get("slides",[])})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}),500

@app.route("/layer2/question",methods=["POST"])
def layer2_question():
    d = request.json
    prompt=f"""Expert instructor. Topic:"{d.get('topic')}" Level:{d.get('level')}. Question:"{d.get('question')}"
WHAT TO SAY:\n[2-3 sentences]\nMISCONCEPTION:\n[1 sentence]\nFOLLOW-UP:\n[1 question]\nQUICK ACTIVITY:\n[2 min activity]"""
    try: return jsonify({"result":ask_groq_text(prompt)})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/layer2/confusion",methods=["POST"])
def layer2_confusion():
    d = request.json
    prompt=f"""Expert instructor. Topic:"{d.get('topic')}" Level:{d.get('level')}. Confusion:"{d.get('confusion')}"
ALTERNATIVE EXPLANATION:\n[New analogy]\nWHAT TO DRAW:\n[Diagram]\n3-MIN RESCUE:\n[Activity]\nRE-ENGAGE:\n[One sentence]"""
    try: return jsonify({"result":ask_groq_text(prompt)})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/layer2/conceptcheck",methods=["POST"])
def layer2_conceptcheck():
    d = request.json; pct=d.get("correct_pct",50)
    prompt=f"""Instructor. Topic:"{d.get('topic')}" Level:{d.get('level')}. Asked:"{d.get('question')}". {pct}% correct.
WHAT THIS MEANS:\n[1-2 sentences]\nNEXT 5 MINUTES:\n[Actions]\nFOLLOW-UP:\n[Question]\nPACING:\n[Advice]"""
    try: return jsonify({"result":ask_groq_text(prompt)})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/layer2/pacing",methods=["POST"])
def layer2_pacing():
    d = request.json
    rem = int(d.get("total_duration",75))-int(d.get("mins_elapsed",0))
    prompt=f"""Instructor. Topic:"{d.get('topic')}" Level:{d.get('level')}. {d.get('total_duration')}min total. {d.get('mins_elapsed')}min elapsed. {rem}min remain. On:"{d.get('current_segment')}".
STATUS:\n[On track/Behind/Ahead]\nWHAT TO DO:\n[Action]\nMUST COVER:\n[Key items]\nWHAT TO CUT:\n[Safe to skip]"""
    try: return jsonify({"result":ask_groq_text(prompt)})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/layer2/student_question",methods=["POST"])
def layer2_student_question():
    d = request.json
    prompt=f"""Friendly tutor. Topic:"{d.get('topic')}". Student: Name={d.get('name')}, Age={d.get('age')}, Year={d.get('year')}, Background={d.get('background')}, Level={d.get('level')}.
Question:"{d.get('question')}"
Personalise to their background. Everyday analogies for non-technical students. Under 200 words. End with encouragement using their name. No headers or bullets."""
    try: return jsonify({"result":ask_groq_text(prompt)})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/generate_video_script",methods=["POST"])
def generate_video_script():
    d = request.json
    prompt=f"""Educational video script for "{d.get('topic')}" ({d.get('level')} level).
INTRO (30s):\n[Hook]\nSEGMENT 1 - WHAT IS IT? (2min):\n[Explanation]\nSEGMENT 2 - HOW IT WORKS (3min):\n[Steps]\nSEGMENT 3 - REAL EXAMPLE (2min):\n[Example]\nSEGMENT 4 - COMMON MISTAKES (1min):\n[Mistakes]\nOUTRO (30s):\n[Summary]"""
    try: return jsonify({"result":ask_groq_text(prompt)})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/generate_slides",methods=["POST"])
def generate_slides():
    d = request.json
    topic=d.get("topic","Topic"); level=d.get("level","Intermediate")
    duration=d.get("duration",75); objectives=d.get("objectives","")
    style=d.get("style","Lecture-based"); slides_data=d.get("slidesData",[])

    GREEN=RGBColor(0x2d,0x6a,0x4f); WHITE=RGBColor(0xFF,0xFF,0xFF); DARK=RGBColor(0x1a,0x1a,0x1a)
    LGRAY=RGBColor(0xF7,0xF5,0xF2); ACCENT=RGBColor(0x74,0xC6,0x9D); DARKGREEN=RGBColor(0x1B,0x43,0x32)
    GRAYTEXT=RGBColor(0xAA,0xAA,0xAA)

    prs = Presentation()
    prs.slide_width=Inches(13.33); prs.slide_height=Inches(7.5)
    blank = prs.slide_layouts[6]

    def add_rect(slide,left,top,width,height,color):
        s=slide.shapes.add_shape(1,Inches(left),Inches(top),Inches(width),Inches(height))
        s.fill.solid(); s.fill.fore_color.rgb=color; s.line.fill.background(); return s

    def add_text(slide,text,left,top,width,height,size=18,bold=False,color=None,align=PP_ALIGN.LEFT):
        tb=slide.shapes.add_textbox(Inches(left),Inches(top),Inches(width),Inches(height))
        tf=tb.text_frame; tf.word_wrap=True
        p=tf.paragraphs[0]; p.alignment=align
        run=p.add_run(); run.text=text
        run.font.size=Pt(size); run.font.bold=bold
        run.font.color.rgb=color if color else DARK

    def add_notes(slide,text):
        if text: slide.notes_slide.notes_text_frame.text=text

    icap_colors={"Passive":RGBColor(0xC0,0x44,0x0A),"Active":RGBColor(0x1A,0x66,0x40),
                 "Constructive":RGBColor(0x1A,0x3F,0x80),"Interactive":RGBColor(0x6A,0x1A,0x80)}
    segments=[
        {"name":"Introduction and Hook","icap":"Active","pct":0.12},
        {"name":"Core Concept Explanation","icap":"Passive","pct":0.35},
        {"name":"Guided In-Class Activity","icap":"Constructive","pct":0.28},
        {"name":"Peer Discussion and Debate","icap":"Interactive","pct":0.13},
        {"name":"Wrap-Up and Reflection","icap":"Constructive","pct":0.12},
    ]

    if slides_data:
        s1=prs.slides.add_slide(blank)
        add_rect(s1,0,0,13.33,7.5,GREEN); add_rect(s1,0,5.8,13.33,1.7,DARKGREEN)
        add_text(s1,"LectureAI",0.5,0.4,12,0.6,size=13,color=ACCENT,align=PP_ALIGN.CENTER)
        add_text(s1,slides_data[0].get("title",topic),0.5,1.2,12,2.2,size=42,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        add_text(s1,level+"  |  "+str(duration)+" min  |  "+style,0.5,3.6,12,0.7,size=17,color=ACCENT,align=PP_ALIGN.CENTER)
        add_notes(s1,slides_data[0].get("speakerNote",""))
        for i,sl in enumerate(slides_data[1:],1):
            s=prs.slides.add_slide(blank)
            s.background.fill.solid(); s.background.fill.fore_color.rgb=LGRAY
            add_rect(s,0,0,13.33,1.2,GREEN)
            add_text(s,sl.get("title","Slide "+str(i+1)),0.4,0.2,12.5,0.85,size=26,bold=True,color=WHITE)
            for j,bul in enumerate(sl.get("bullets",[])[:7]):
                y=1.4+j*0.76; add_rect(s,0.4,y+0.1,0.12,0.12,ACCENT)
                add_text(s,bul,0.7,y,12,0.72,size=16,color=DARK)
            add_notes(s,sl.get("speakerNote",""))
    else:
        s1=prs.slides.add_slide(blank)
        add_rect(s1,0,0,13.33,7.5,GREEN); add_rect(s1,0,5.8,13.33,1.7,DARKGREEN)
        add_text(s1,"LectureAI",0.5,0.4,12,0.6,size=13,color=ACCENT,align=PP_ALIGN.CENTER)
        add_text(s1,topic,0.5,1.2,12,2.2,size=42,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        add_text(s1,level+"  |  "+str(duration)+" min  |  "+style,0.5,3.6,12,0.7,size=17,color=ACCENT,align=PP_ALIGN.CENTER)
        s2=prs.slides.add_slide(blank)
        s2.background.fill.solid(); s2.background.fill.fore_color.rgb=LGRAY
        add_rect(s2,0,0,13.33,1.2,GREEN)
        add_text(s2,"Learning Objectives",0.4,0.2,12,0.85,size=26,bold=True,color=WHITE)
        obj_lines=objectives.strip().split("\n") if objectives else ["Understand key concepts","Apply the methods","Evaluate results"]
        for i,obj in enumerate(obj_lines[:6]):
            y=1.5+i*0.85; add_rect(s2,0.5,y,0.4,0.55,GREEN)
            add_text(s2,str(i+1),0.5,y+0.05,0.4,0.45,size=15,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
            add_text(s2,obj.lstrip("0123456789. "),1.1,y+0.08,11.7,0.5,size=16,color=DARK)
        for i,seg in enumerate(segments):
            s=prs.slides.add_slide(blank)
            s.background.fill.solid(); s.background.fill.fore_color.rgb=LGRAY
            add_rect(s,0,0,13.33,1.2,GREEN)
            add_text(s,"Segment "+str(i+1),0.4,0.05,4,0.38,size=11,color=ACCENT)
            add_text(s,seg["name"],0.4,0.38,10,0.75,size=24,bold=True,color=WHITE)
            mins=max(5,round(duration*seg["pct"]))
            add_text(s,str(mins)+" min",10.5,0.38,2.5,0.65,size=19,bold=True,color=ACCENT,align=PP_ALIGN.RIGHT)
            ic=icap_colors.get(seg["icap"],GREEN)
            add_rect(s,0.4,1.5,2.1,0.48,ic)
            add_text(s,seg["icap"].upper(),0.4,1.52,2.1,0.44,size=12,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
            add_text(s,"Topic: "+topic,0.4,2.2,12.5,0.48,size=17,bold=True,color=GREEN)
            add_text(s,"Use "+style.lower()+" for "+level.lower()+"-level learners.",0.4,2.85,12.5,0.55,size=15,color=DARK)
            add_rect(s,0.4,4.8,12.4,1.85,WHITE)
            add_text(s,"Instructor notes...",0.6,4.9,12,1.6,size=13,color=GRAYTEXT)
        sc=prs.slides.add_slide(blank)
        add_rect(sc,0,0,13.33,7.5,GREEN); add_rect(sc,0,5.5,13.33,2.0,DARKGREEN)
        add_text(sc,"Thank You",0.5,2.0,12,1.5,size=52,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        add_text(sc,"Any questions about "+topic+"?",0.5,3.6,12,0.8,size=22,color=ACCENT,align=PP_ALIGN.CENTER)

    buf=io.BytesIO(); prs.save(buf); buf.seek(0)
    filename="LectureAI_"+topic.replace(" ","_")+".pptx"
    return send_file(buf,as_attachment=True,download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation")

if __name__=="__main__":
    app.run(debug=True)
