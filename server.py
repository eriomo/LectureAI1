import os, json, io, sqlite3, uuid, re
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from groq import Groq
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
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

# ── Class management ──────────────────────────────────────────
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

# ── Assignments ───────────────────────────────────────────────
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

# ── Tests ─────────────────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════
#  ICAP-ALIGNED LECTURE NOTES (with language support)
# ══════════════════════════════════════════════════════════════
@app.route("/generate_notes", methods=["POST"])
def generate_notes():
    try:
        d = request.json
        topic = d.get("topic",""); level = d.get("level","Intermediate")
        duration = d.get("duration",75); objectives = d.get("objectives","")
        style = d.get("style","Lecture-based")
        language = d.get("language","English")

        p = f"""You are an expert university lecturer designing a comprehensive {duration}-minute {level}-level lecture on "{topic}" using a {style} approach.

IMPORTANT: Write the ENTIRE response in {language}. All section headings, content, and explanations must be in {language}.

Learning objectives:
{objectives if objectives else "Cover the topic comprehensively for " + level + "-level learners."}

You MUST structure the notes following the ICAP pedagogical framework (Chi & Wylie, 2014). Each section must be labeled with its ICAP engagement level. Use EXACTLY these section headers and ICAP tags:

[PASSIVE] 1. INTRODUCTION AND CONTEXT
- Why this topic matters in the real world
- Historical context and evolution of this concept
- Where this fits in the broader curriculum
- A compelling hook or story to open the lecture
- At least 3 paragraphs of detailed context

[PASSIVE] 2. CORE DEFINITIONS AND TERMINOLOGY
- Define every key term precisely with examples
- Provide formal definitions alongside plain-language explanations
- Include at least 6-8 key terms
- Use analogies from everyday life to ground abstract concepts

[ACTIVE] 3. DETAILED CONCEPT EXPLANATIONS
- Deep dive into each concept with step-by-step reasoning
- Multiple representations: verbal, mathematical, visual descriptions
- At least 3-4 major concepts each with 2+ paragraphs
- Connect concepts to each other — show the "big picture"
- Highlight what makes each concept non-obvious or surprising

[ACTIVE] 4. WORKED EXAMPLES WITH ANNOTATIONS
- Provide at least 3 fully worked examples of increasing difficulty
- For each example: state the problem, show every step, explain WHY each step is taken
- Include common wrong approaches and why they fail
- Use concrete, realistic data or scenarios

[CONSTRUCTIVE] 5. CRITICAL THINKING CHALLENGES
- Pose 3-4 open-ended questions that require analysis, not just recall
- Include "what if" scenarios that push students to extend concepts
- Provide a mini case study where students must apply multiple concepts together
- Ask students to generate their own examples or explanations
- Include a "teach it back" prompt: "How would you explain this to someone who has never heard of it?"

[CONSTRUCTIVE] 6. COMMON MISCONCEPTIONS AND DEBUGGING
- List at least 5 common errors or misunderstandings
- For each: explain WHY the misconception is intuitive, then clarify the correct understanding
- Include "tricky edge cases" that test deep understanding

[INTERACTIVE] 7. COLLABORATIVE ACTIVITIES
- Design a pair/group discussion activity (3-5 minutes) with specific prompts
- Include a think-pair-share question
- Design a mini-debate or argument-mapping exercise
- Provide a peer-teaching activity where students explain concepts to each other
- Include a polling/clicker-style question with answer choices and discussion points

[INTERACTIVE] 8. REAL-WORLD APPLICATION PROJECT
- Present a substantial real-world scenario or dataset
- Guide students through applying the lecture concepts to solve it collaboratively
- Include roles for different group members
- Include reflection questions: "What surprised you?" "What would you do differently?"

[PASSIVE] 9. SUMMARY AND KEY TAKEAWAYS
- Bullet-point recap of every major concept
- A "cheat sheet" of the most important formulas, rules, or principles
- Connections to the next lecture topic

[CONSTRUCTIVE] 10. SELF-ASSESSMENT AND REFLECTION
- 5 self-check questions (mix of recall, application, and analysis)
- A metacognitive prompt: "What was the hardest part for you? Why?"
- Suggested further reading: 3-4 specific topics or resources
- A "one-minute paper" prompt for students to summarize their learning

Write in clear, engaging academic language. Be THOROUGH — these notes should be detailed enough for a student to study from independently. Each section should be substantial (not just a few bullet points). Aim for at least 2500 words total. Use markdown-style formatting with headers, sub-points, and emphasis where appropriate."""

        result = ask_groq(p, max_tokens=4000)
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


# ══════════════════════════════════════════════════════════════
#  AI SLIDESHOW DATA (for in-browser presentation with TTS)
# ══════════════════════════════════════════════════════════════
@app.route("/generate_slideshow_data", methods=["POST"])
def generate_slideshow_data():
    try:
        d = request.json
        topic = d.get("topic","Topic"); level = d.get("level","Intermediate")
        duration = d.get("duration",75); notes = d.get("notes","")
        language = d.get("language","English")

        # Use notes excerpt if available, otherwise topic only
        context = f"Based on these lecture notes:\n{notes[:2000]}" if notes and len(notes) > 50 else f"Topic: {topic}"

        # Simpler, more reliable prompt - fewer slides, cleaner JSON
        p = f"""{context}

Create 10 lecture slides for "{topic}" at {level} level in {language}.

RESPOND WITH ONLY A JSON ARRAY. No text before or after. No markdown backticks.

Each slide object:
{{"title":"string","bullets":["string","string","string"],"narration":"string","icap":"passive","type":"content"}}

The 10 slides:
1. title slide: title="{topic}", bullets=["{level} level","{duration} minutes","Human-AI Co-Orchestration"], narration="Welcome...", type="title"
2. objectives: 3-4 learning goals, icap="passive", type="content"
3. key definitions: 3-4 terms defined, icap="passive", type="content"
4. concept 1: main idea explained in 3-4 points, icap="active", type="content"
5. concept 2: second idea in 3-4 points, icap="active", type="content"
6. worked example: step-by-step in 4 points, icap="active", type="example"
7. misconceptions: 3 common errors, icap="constructive", type="content"
8. discussion activity: 3 prompts for pair work, icap="interactive", type="activity"
9. key takeaways: 4 summary points, icap="passive", type="summary"
10. closing: next steps and thank you, type="title"

Each narration should be 20-40 words of natural speech. Each bullet must be a full sentence.
Return ONLY the JSON array, starting with [ and ending with ]."""

        result = ask_groq(p, max_tokens=2500)

        # Robust JSON extraction - try multiple approaches
        slides = None

        # Try 1: direct parse
        try:
            slides = json.loads(result)
        except:
            pass

        # Try 2: find array in text
        if not slides:
            try:
                match = re.search(r'\[[\s\S]*\]', result)
                if match:
                    slides = json.loads(match.group())
            except:
                pass

        # Try 3: strip markdown fences
        if not slides:
            try:
                cleaned = re.sub(r'^```(?:json)?\s*', '', result.strip())
                cleaned = re.sub(r'\s*```$', '', cleaned.strip())
                slides = json.loads(cleaned)
            except:
                pass

        if slides and isinstance(slides, list) and len(slides) > 0:
            return jsonify({"success": True, "slides": slides})
        else:
            # Return the raw text so the client can see what went wrong
            return jsonify({"success": False, "error": "AI did not return valid slides. Using local fallback.", "raw": result[:500]})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


# ══════════════════════════════════════════════════════════════
#  STUDY PLAN GENERATOR
# ══════════════════════════════════════════════════════════════
@app.route("/generate_study_plan", methods=["POST"])
def generate_study_plan():
    try:
        d = request.json
        topic = d.get("topic",""); level = d.get("level","Intermediate")
        background = d.get("background",""); language = d.get("language","English")
        p = f"""Create a personalized 7-day study plan for a student studying "{topic}" at {level} level.
Student background: {background if background else 'General learner'}.
Write in {language}.

Include for each day:
- Study focus (30-60 minutes)
- Specific tasks to complete
- One self-check question
- A tip for the day

End with 3 recommended resources (books, videos, websites).
Be specific and actionable."""
        result = ask_groq(p, max_tokens=1500)
        return jsonify({"success": True, "plan": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── Layer 2: Real-time orchestration ─────────────────────────
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

# ── AI feedback on assignment ────────────────────────────────
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

# ── AI quiz generator ────────────────────────────────────────
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

# ── Emoji reactions ──────────────────────────────────────────
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

# ── Attendance tracker ───────────────────────────────────────
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

# ── Discussion board ─────────────────────────────────────────
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


# ══════════════════════════════════════════════════════════════
#  POWERPOINT GENERATION (Massively improved)
# ══════════════════════════════════════════════════════════════
@app.route("/generate_slides", methods=["POST"])
def generate_slides():
    try:
        d = request.json
        topic = d.get("topic","Topic"); level = d.get("level","Intermediate")
        duration = d.get("duration",75); objectives = d.get("objectives","")
        style = d.get("style","Lecture-based"); notes = d.get("notes","")

        # ── Colors ──
        GREEN = RGBColor(0x2d,0x6a,0x4f)
        WHITE = RGBColor(0xFF,0xFF,0xFF)
        DARK = RGBColor(0x1a,0x1a,0x1a)
        LGRAY = RGBColor(0xF7,0xF5,0xF2)
        ACCENT = RGBColor(0x74,0xC6,0x9D)
        DKGREEN = RGBColor(0x1B,0x43,0x32)
        GOLD = RGBColor(0xF4,0xA2,0x61)
        SOFTWHITE = RGBColor(0xEC,0xEC,0xEC)

        prs = Presentation()
        prs.slide_width = Inches(13.33)
        prs.slide_height = Inches(7.5)
        blank = prs.slide_layouts[6]

        def rect(slide,l,t,w,h,c):
            s = slide.shapes.add_shape(1,Inches(l),Inches(t),Inches(w),Inches(h))
            s.fill.solid(); s.fill.fore_color.rgb=c; s.line.fill.background(); return s

        def txt(slide,text,l,t,w,h,sz=18,bold=False,color=None,align=PP_ALIGN.LEFT):
            tb = slide.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h))
            tf = tb.text_frame; tf.word_wrap = True; p = tf.paragraphs[0]; p.alignment = align
            run = p.add_run(); run.text = text; run.font.size = Pt(sz)
            run.font.bold = bold; run.font.color.rgb = color if color else DARK

        def multi_txt(slide, lines, l, t, w, h, sz=16, color=None, spacing=0.5):
            """Add multiple lines of text with bullet markers"""
            tb = slide.shapes.add_textbox(Inches(l),Inches(t),Inches(w),Inches(h))
            tf = tb.text_frame; tf.word_wrap = True
            for i, line in enumerate(lines):
                if i == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.space_before = Pt(6)
                p.space_after = Pt(4)
                run = p.add_run()
                run.text = line
                run.font.size = Pt(sz)
                run.font.color.rgb = color if color else DARK

        # ── First, generate slide content from AI if notes are sparse ──
        slide_sections = []
        if notes and len(notes) > 200:
            # Parse ICAP-tagged sections from notes
            icap_pattern = r'\[(?:PASSIVE|ACTIVE|CONSTRUCTIVE|INTERACTIVE)\]\s*\d+\.\s*([^\n]+)'
            headers = re.findall(icap_pattern, notes)
            sections = re.split(r'\[(?:PASSIVE|ACTIVE|CONSTRUCTIVE|INTERACTIVE)\]\s*\d+\.', notes)
            icap_tags = re.findall(r'\[(PASSIVE|ACTIVE|CONSTRUCTIVE|INTERACTIVE)\]', notes)

            for i, header in enumerate(headers[:10]):
                content = sections[i+1] if i+1 < len(sections) else ""
                lines = [re.sub(r'^[\s•\-\*\d\.]+','',l).strip() for l in content.split('\n')]
                lines = [l for l in lines if len(l) > 10][:6]
                tag = icap_tags[i] if i < len(icap_tags) else "PASSIVE"
                if lines:
                    slide_sections.append({
                        "title": header.strip(),
                        "bullets": lines,
                        "icap": tag
                    })

        # If parsing didn't yield enough, use fallback structured content
        if len(slide_sections) < 5:
            # Generate structured content from AI
            gen_prompt = f"""For a {level}-level lecture on "{topic}", provide slide content.
Return ONLY valid JSON array, no markdown:
[
  {{"title":"Learning Objectives","bullets":["Obj 1","Obj 2","Obj 3","Obj 4"],"icap":"PASSIVE"}},
  {{"title":"Why This Matters","bullets":["Point 1","Point 2","Point 3"],"icap":"PASSIVE"}},
  {{"title":"Core Concept: Definition","bullets":["Detail 1","Detail 2","Detail 3","Detail 4"],"icap":"ACTIVE"}},
  {{"title":"Core Concept: How It Works","bullets":["Step 1","Step 2","Step 3","Step 4"],"icap":"ACTIVE"}},
  {{"title":"Core Concept: Key Properties","bullets":["Property 1","Property 2","Property 3"],"icap":"ACTIVE"}},
  {{"title":"Worked Example 1","bullets":["Problem setup","Step 1","Step 2","Result"],"icap":"ACTIVE"}},
  {{"title":"Worked Example 2","bullets":["Problem setup","Step 1","Step 2","Result"],"icap":"ACTIVE"}},
  {{"title":"Common Misconceptions","bullets":["Mistake 1 and why","Mistake 2 and why","Mistake 3 and why"],"icap":"CONSTRUCTIVE"}},
  {{"title":"Think-Pair-Share Activity","bullets":["Discussion prompt 1","Discussion prompt 2","Reflection question"],"icap":"INTERACTIVE"}},
  {{"title":"Real-World Applications","bullets":["Application 1","Application 2","Application 3"],"icap":"CONSTRUCTIVE"}},
  {{"title":"Group Challenge","bullets":["Task description","What to discuss","How to present findings"],"icap":"INTERACTIVE"}},
  {{"title":"Key Takeaways","bullets":["Takeaway 1","Takeaway 2","Takeaway 3","Takeaway 4"],"icap":"PASSIVE"}}
]
Make every bullet a complete, informative sentence about {topic}."""
            try:
                ai_result = ask_groq(gen_prompt, max_tokens=2000)
                match = re.search(r'\[.*\]', ai_result, re.DOTALL)
                if match:
                    slide_sections = json.loads(match.group())
            except:
                pass

        # Final fallback
        if len(slide_sections) < 3:
            objs = [o.strip() for o in objectives.split('\n') if o.strip()][:5]
            slide_sections = [
                {"title":"Learning Objectives","bullets":objs or [f"Understand the fundamentals of {topic}",f"Apply {topic} concepts to real problems","Evaluate results critically","Connect theory to practice"],"icap":"PASSIVE"},
                {"title":"Why This Matters","bullets":[f"Real-world relevance of {topic}",f"Where {topic} is applied today","What problem it solves","Why professionals need this skill"],"icap":"PASSIVE"},
                {"title":"Core Concepts","bullets":[f"Fundamental principles of {topic}","Key terminology and definitions","How the components connect","The underlying logic and reasoning"],"icap":"ACTIVE"},
                {"title":"Detailed Explanation","bullets":[f"Deep dive into the mechanics of {topic}","Step-by-step breakdown of the process","Multiple ways to think about this concept","What makes it different from related ideas"],"icap":"ACTIVE"},
                {"title":"Worked Example 1","bullets":["Problem statement and setup","Step 1: Identify what we know","Step 2: Apply the method","Step 3: Interpret the result"],"icap":"ACTIVE"},
                {"title":"Worked Example 2","bullets":["A more challenging scenario","Breaking down the complexity","Applying multiple concepts together","Verifying our answer makes sense"],"icap":"ACTIVE"},
                {"title":"Common Misconceptions","bullets":["Confusing similar but different concepts","Skipping assumptions that matter","Overfitting a method to every problem","Ignoring edge cases and limitations"],"icap":"CONSTRUCTIVE"},
                {"title":"Think-Pair-Share","bullets":["Discuss with your neighbor: What is the key insight?","Come up with your own example","Identify one thing you are unsure about","Prepare to share with the class"],"icap":"INTERACTIVE"},
                {"title":"Real-World Application","bullets":[f"How {topic} is used in industry","A case study from recent research","Connecting theory to professional practice","What practitioners wish they learned earlier"],"icap":"CONSTRUCTIVE"},
                {"title":"Group Challenge","bullets":["Work in groups of 3-4","Apply today's concepts to this scenario","Prepare a 2-minute explanation","Be ready for questions from peers"],"icap":"INTERACTIVE"},
                {"title":"Key Takeaways","bullets":[f"Core idea: understand {topic} by doing it","Start with intuition, then formalize","Practice with varied examples","Connect each concept to the big picture"],"icap":"PASSIVE"},
                {"title":"Self-Assessment","bullets":["Can you explain the key concept in your own words?","Could you solve a new problem using today's methods?","What would you review before an exam?","Write down one remaining question"],"icap":"CONSTRUCTIVE"},
            ]

        # ── ICAP color mapping ──
        ICAP_COLORS = {
            "PASSIVE": RGBColor(0x6C,0x75,0x7D),
            "ACTIVE": RGBColor(0x0D,0x6E,0xFD),
            "CONSTRUCTIVE": RGBColor(0xF4,0xA2,0x61),
            "INTERACTIVE": RGBColor(0xE6,0x39,0x46),
        }
        ICAP_LABELS = {
            "PASSIVE": "PASSIVE — Receiving",
            "ACTIVE": "ACTIVE — Manipulating",
            "CONSTRUCTIVE": "CONSTRUCTIVE — Generating",
            "INTERACTIVE": "INTERACTIVE — Dialoguing",
        }

        # ══ SLIDE 1: Title ══
        s1 = prs.slides.add_slide(blank)
        rect(s1,0,0,13.33,7.5,GREEN)
        rect(s1,0,5.6,13.33,1.9,DKGREEN)
        # Decorative accent line
        rect(s1,0.5,4.8,12.33,0.04,ACCENT)
        txt(s1,"LectureAI",0.5,0.4,12,0.5,sz=14,color=ACCENT,align=PP_ALIGN.CENTER)
        txt(s1,topic,0.5,1.2,12,2.5,sz=44,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        subtitle = f"{level} | {duration} min | {style}"
        txt(s1,subtitle,0.5,3.6,12,0.7,sz=18,color=ACCENT,align=PP_ALIGN.CENTER)
        txt(s1,"Human-AI Co-Orchestration in Education",0.5,6.0,12,0.5,sz=13,color=SOFTWHITE,align=PP_ALIGN.CENTER)
        txt(s1,"Powered by ICAP Framework (Chi & Wylie, 2014)",0.5,6.5,12,0.5,sz=11,color=ACCENT,align=PP_ALIGN.CENTER)

        # ══ SLIDE 2: ICAP Framework Overview ══
        s2 = prs.slides.add_slide(blank)
        rect(s2,0,0,13.33,7.5,LGRAY)
        rect(s2,0,0,13.33,1.4,GREEN)
        txt(s2,"ICAP Framework: How This Lecture Is Designed",0.4,0.2,12.5,1.0,sz=28,bold=True,color=WHITE)
        txt(s2,"LectureAI",11.5,0.22,1.5,0.5,sz=10,color=ACCENT)
        # ICAP boxes
        icap_items = [
            ("PASSIVE","Receiving information\nListening, reading, watching","#6C757D"),
            ("ACTIVE","Manipulating materials\nHighlighting, copying, repeating","#0D6EFD"),
            ("CONSTRUCTIVE","Generating new outputs\nExplaining, creating, hypothesizing","#F4A261"),
            ("INTERACTIVE","Dialoguing with peers\nDebating, teaching, co-creating","#E63946"),
        ]
        x_start = 0.5
        for idx, (label, desc, hex_c) in enumerate(icap_items):
            bx = x_start + idx * 3.1
            r_int = int(hex_c[1:3],16); g_int = int(hex_c[3:5],16); b_int = int(hex_c[5:7],16)
            c = RGBColor(r_int, g_int, b_int)
            rect(s2, bx, 1.8, 2.9, 0.12, c)
            txt(s2, label, bx+0.1, 2.1, 2.7, 0.6, sz=22, bold=True, color=DARK)
            desc_lines = desc.split('\n')
            for li, line in enumerate(desc_lines):
                txt(s2, line, bx+0.1, 2.8+li*0.4, 2.7, 0.4, sz=13, color=DARK)
        txt(s2,"Higher engagement levels produce deeper learning outcomes (Chi & Wylie, 2014)",0.5,5.2,12.33,0.5,sz=14,bold=True,color=GREEN)
        txt(s2,"This lecture follows ICAP: starting with foundational knowledge, building toward active application, then constructive analysis, and finally interactive collaboration.",
            0.5,5.8,12.33,1.0,sz=13,color=DARK)

        # ══ CONTENT SLIDES ══
        for idx, section in enumerate(slide_sections):
            s = prs.slides.add_slide(blank)
            is_dark = idx % 2 == 1
            bg = DKGREEN if is_dark else LGRAY
            text_c = WHITE if is_dark else DARK

            rect(s, 0, 0, 13.33, 7.5, bg)
            rect(s, 0, 0, 13.33, 1.4, GREEN)

            title_text = section.get("title","")
            icap_tag = section.get("icap","PASSIVE").upper()

            txt(s, title_text, 0.4, 0.2, 10.5, 1.0, sz=28, bold=True, color=WHITE)
            txt(s, "LectureAI", 11.5, 0.22, 1.5, 0.5, sz=10, color=ACCENT)

            # ICAP badge
            icap_color = ICAP_COLORS.get(icap_tag, ACCENT)
            icap_label = ICAP_LABELS.get(icap_tag, icap_tag)
            badge = rect(s, 0.4, 1.5, 3.0, 0.35, icap_color)
            txt(s, icap_label, 0.5, 1.52, 2.8, 0.3, sz=11, bold=True, color=WHITE)

            # Slide number
            txt(s, f"Slide {idx+3}", 12.0, 1.52, 1.0, 0.3, sz=10, color=ACCENT if is_dark else GREEN)

            # Bullet content
            bullets = section.get("bullets", [])[:6]
            y = 2.1
            for b in bullets:
                # Accent bar
                rect(s, 0.5, y+0.05, 0.06, 0.35, ACCENT)
                txt(s, str(b), 0.75, y, 12.0, 0.5, sz=16, color=text_c)
                y += 0.65

        # ══ THANK YOU SLIDE ══
        sc = prs.slides.add_slide(blank)
        rect(sc,0,0,13.33,7.5,DKGREEN)
        rect(sc,0.5,3.0,12.33,0.04,ACCENT)
        txt(sc,"Thank You",0.5,1.2,12,1.5,sz=52,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
        txt(sc,f"Questions about {topic}?",0.5,3.3,12,0.8,sz=24,color=ACCENT,align=PP_ALIGN.CENTER)
        txt(sc,"Key Reminder: The best way to learn is to explain it to someone else.",
            0.5,4.5,12,0.6,sz=15,color=SOFTWHITE,align=PP_ALIGN.CENTER)
        txt(sc,"Built with LectureAI · Human-AI Co-Orchestration · ICAP Framework",
            0.5,6.5,12,0.6,sz=12,color=ACCENT,align=PP_ALIGN.CENTER)

        buf = io.BytesIO()
        prs.save(buf); buf.seek(0)
        return send_file(buf,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            as_attachment=True,
            download_name=f"LectureAI_{topic[:30].replace(' ','_')}.pptx")
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
