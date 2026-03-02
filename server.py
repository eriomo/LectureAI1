import os
import re
import json
import io
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

# ── HELPER: call the AI ───────────────────────────────────────────────────────

def ask_groq(prompt, max_tokens=1500):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content

# ── HELPER: clean messy AI JSON responses ─────────────────────────────────────

def clean_json(raw):
    # Step 1: remove markdown code fences
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    # Step 2: find the JSON object inside the text
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    # Step 3: fix broken backslashes
    raw = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
    return raw.strip()

# ── HELPER: plain text response for Layer 2 tools ────────────────────────────

def ask_groq_text(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    return open(path).read()

# ── LESSON PLAN GENERATION ────────────────────────────────────────────────────

@app.route("/generate", methods=["POST"])
def generate():
    d          = request.json
    topic      = d.get("topic", "")
    objectives = d.get("objectives", "")
    level      = d.get("level", "Intermediate")
    duration   = d.get("duration", 75)
    style      = d.get("style", "Lecture-based")

    prompt = f"""
You are an expert instructional designer for data science education.
Generate a complete lesson plan as a JSON object. Return ONLY the JSON — no extra text, no markdown.

Topic: {topic}
Level: {level}
Duration: {duration} minutes
Teaching Style: {style}
Learning Objectives: {objectives}

Return this exact JSON structure:
{{
  "outline": [
    {{"segment": "...", "icap": "Passive|Active|Constructive|Interactive", "duration_mins": 0, "description": "..."}}
  ],
  "analogies": ["...", "...", "..."],
  "activities": [
    {{"title": "...", "icap": "...", "prompt": "..."}}
  ],
  "reflections": ["...", "...", "...", "..."],
  "micro_explanation": "...",
  "practice_questions": [
    {{"difficulty": "Easy|Medium|Hard", "question": "...", "hint": "..."}}
  ],
  "srl_prompts": ["...", "...", "...", "..."]
}}
"""
    try:
        raw    = ask_groq(prompt, max_tokens=2000)
        clean  = clean_json(raw)
        result = json.loads(clean)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ── LAYER 2: TEACHER QUESTION HANDLER ────────────────────────────────────────

@app.route("/layer2/question", methods=["POST"])
def layer2_question():
    d        = request.json
    question = d.get("question", "")
    topic    = d.get("topic", "")
    level    = d.get("level", "")

    prompt = f"""
You are an expert data science instructor. A student just asked the following question during a live lecture on "{topic}" for {level}-level students.

Student question: "{question}"

Give the instructor a response they can use immediately. Be practical and direct.

Format your response like this:

WHAT TO SAY:
[2-3 sentences the instructor can say out loud right now]

MISCONCEPTION BEHIND THIS QUESTION:
[1 sentence explaining what the student misunderstood]

FOLLOW-UP FOR THE CLASS:
[1 question to ask the whole class to check understanding]

QUICK ACTIVITY (2 minutes):
[A simple activity to reinforce the concept right now]
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── LAYER 2: CONFUSION DETECTOR ──────────────────────────────────────────────

@app.route("/layer2/confusion", methods=["POST"])
def layer2_confusion():
    d        = request.json
    confusion = d.get("confusion", "")
    topic    = d.get("topic", "")
    level    = d.get("level", "")

    prompt = f"""
You are an expert data science instructor. During a live lecture on "{topic}" for {level}-level students, the instructor has noticed the following confusion:

"{confusion}"

Give the instructor an immediate rescue strategy. Be practical and direct.

Format your response like this:

ALTERNATIVE EXPLANATION:
[Explain the concept in a completely different way using a new analogy]

WHAT TO DRAW ON THE WHITEBOARD:
[Describe a simple diagram or visual the instructor can draw right now]

3-MINUTE RESCUE ACTIVITY:
[A quick activity to re-engage students and fix the confusion]

PHRASE TO RE-ENGAGE THE CLASS:
[One sentence the instructor can say to bring the class back]
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── LAYER 2: CONCEPT CHECK INTERPRETER ───────────────────────────────────────

@app.route("/layer2/conceptcheck", methods=["POST"])
def layer2_conceptcheck():
    d           = request.json
    question    = d.get("question", "")
    correct_pct = d.get("correct_pct", 50)
    topic       = d.get("topic", "")
    level       = d.get("level", "")

    prompt = f"""
You are an expert data science instructor teaching "{topic}" to {level}-level students.
The instructor asked the class: "{question}"
{correct_pct}% of students answered correctly.

Give the instructor specific guidance. Be practical and direct.

Format your response like this:

WHAT THIS MEANS:
[1-2 sentences on what {correct_pct}% correct tells you about student understanding]

WHAT TO DO IN THE NEXT 5 MINUTES:
[Specific actions based on the percentage]

FOLLOW-UP QUESTION TO ASK NOW:
[One question to probe deeper or confirm understanding]

PACING ADVICE:
[Should the instructor move on, slow down, or revisit?]
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── LAYER 2: PACING ASSISTANT ─────────────────────────────────────────────────

@app.route("/layer2/pacing", methods=["POST"])
def layer2_pacing():
    d               = request.json
    mins_elapsed    = d.get("mins_elapsed", 0)
    current_segment = d.get("current_segment", "")
    topic           = d.get("topic", "")
    level           = d.get("level", "")
    total_duration  = d.get("total_duration", 75)
    mins_remaining  = int(total_duration) - int(mins_elapsed)

    prompt = f"""
You are an expert data science instructor teaching "{topic}" to {level}-level students.
The class is {total_duration} minutes total.
{mins_elapsed} minutes have passed. {mins_remaining} minutes remain.
The instructor is currently on: "{current_segment}"

Give specific pacing advice. Be practical and direct.

Format your response like this:

STATUS:
[On track / Behind / Ahead — and by how much]

WHAT TO DO:
[Specific adjustment to make right now]

MUST COVER BEFORE END:
[The 1-2 most important things that cannot be skipped]

WHAT CAN BE CUT OR SHORTENED:
[What is safe to skip or rush through if needed]
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── LAYER 2: STUDENT PERSONALISED QUESTION ────────────────────────────────────

@app.route("/layer2/student_question", methods=["POST"])
def layer2_student_question():
    d          = request.json
    question   = d.get("question", "")
    topic      = d.get("topic", "")
    level      = d.get("level", "")
    name       = d.get("name", "Student")
    age        = d.get("age", "unknown")
    year       = d.get("year", "unknown")
    background = d.get("background", "unknown")

    prompt = f"""
You are a patient and friendly data science tutor. A student is asking you a question during a lecture on "{topic}".

About this student:
- Name: {name}
- Age: {age}
- Year of study: {year}
- Academic background: {background}
- Current class level: {level}

The student asked: "{question}"

Give a personalised explanation tailored specifically to this student's age, background, and level.
- If they have a non-technical background, use everyday analogies from their world
- If they are a first-year student, avoid jargon and build from the basics
- If they are advanced, you can use more technical language
- Keep your answer friendly, clear, and under 200 words
- End with one encouraging sentence addressed to them by name

Do not use headers or bullet points. Write it like you are talking directly to {name}.
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── SLIDE GENERATION ──────────────────────────────────────────────────────────

@app.route("/generate_slides", methods=["POST"])
def generate_slides():
    d          = request.json
    topic      = d.get("topic", "Topic")
    level      = d.get("level", "Intermediate")
    duration   = d.get("duration", 75)
    objectives = d.get("objectives", "")
    style      = d.get("style", "Lecture-based")

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)

    GREEN  = RGBColor(0x2d, 0x6a, 0x4f)
    WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
    DARK   = RGBColor(0x1a, 0x1a, 0x1a)
    LGRAY  = RGBColor(0xF7, 0xF5, 0xF2)
    ACCENT = RGBColor(0x74, 0xC6, 0x9D)

    blank_layout = prs.slide_layouts[6]  # completely blank

    def add_rect(slide, left, top, width, height, color):
        shape = slide.shapes.add_shape(1, Inches(left), Inches(top), Inches(width), Inches(height))
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        return shape

    def add_text(slide, text, left, top, width, height,
                 size=18, bold=False, color=None, align=PP_ALIGN.LEFT, wrap=True):
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = wrap
        p  = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color if color else DARK
        return tb

    # ── SLIDE 1: TITLE ──────────────────────────────────────────────────────
    s1 = prs.slides.add_slide(blank_layout)
    add_rect(s1, 0, 0, 13.33, 7.5, GREEN)
    add_rect(s1, 0, 5.8, 13.33, 1.7, RGBColor(0x1B, 0x43, 0x32))
    add_text(s1, "🎓 LectureAI",   0.5, 0.5, 12, 1.2, size=14, bold=False, color=ACCENT, align=PP_ALIGN.CENTER)
    add_text(s1, topic,             0.5, 1.4, 12, 2.0, size=44, bold=True,  color=WHITE,  align=PP_ALIGN.CENTER)
    add_text(s1, f"{level} Level  ·  {duration} Minutes  ·  {style}", 0.5, 3.6, 12, 0.7, size=18, color=ACCENT, align=PP_ALIGN.CENTER)
    add_text(s1, "Generated by LectureAI", 0.5, 6.0, 12, 0.6, size=12, color=RGBColor(0xAA,0xAA,0xAA), align=PP_ALIGN.CENTER)

    # ── SLIDE 2: LEARNING OBJECTIVES ────────────────────────────────────────
    s2 = prs.slides.add_slide(blank_layout)
    s2.background.fill.solid()
    s2.background.fill.fore_color.rgb = LGRAY
    add_rect(s2, 0, 0, 13.33, 1.3, GREEN)
    add_text(s2, "Learning Objectives", 0.5, 0.1, 12, 1.0, size=32, bold=True, color=WHITE)
    obj_lines = objectives.strip().split("\n") if objectives else ["Understand the key concepts", "Apply the methods", "Evaluate the results"]
    for i, obj in enumerate(obj_lines[:6]):
        y = 1.6 + i * 0.85
        add_rect(s2, 0.5, y, 0.35, 0.55, GREEN)
        add_text(s2, str(i+1), 0.5, y+0.02, 0.35, 0.5, size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s2, obj.lstrip("0123456789. "), 1.1, y+0.03, 11.5, 0.55, size=16, color=DARK)

    # ── SLIDES 3-7: ONE PER SEGMENT ─────────────────────────────────────────
    segments = [
        {"name":"Introduction & Hook",      "icap":"Active",       "pct":0.12},
        {"name":"Core Concept Explanation",  "icap":"Passive",      "pct":0.35},
        {"name":"Guided In-Class Activity",  "icap":"Constructive", "pct":0.28},
        {"name":"Peer Discussion & Debate",  "icap":"Interactive",  "pct":0.13},
        {"name":"Wrap-Up & Reflection",      "icap":"Constructive", "pct":0.12},
    ]
    icap_colors = {
        "Passive":      RGBColor(0xC0,0x44,0x0A),
        "Active":       RGBColor(0x1A,0x66,0x40),
        "Constructive": RGBColor(0x1A,0x3F,0x80),
        "Interactive":  RGBColor(0x6A,0x1A,0x80),
    }

    for i, seg in enumerate(segments):
        s = prs.slides.add_slide(blank_layout)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = LGRAY
        add_rect(s, 0, 0, 13.33, 1.3, GREEN)
        add_text(s, f"Segment {i+1} of {len(segments)}", 0.5, 0.05, 6, 0.45, size=11, color=ACCENT)
        add_text(s, seg["name"], 0.5, 0.45, 10, 0.75, size=26, bold=True, color=WHITE)
        mins = max(5, round(duration * seg["pct"]))
        add_text(s, f"{mins} minutes", 10.5, 0.5, 2.5, 0.6, size=18, bold=True, color=ACCENT, align=PP_ALIGN.RIGHT)
        ic_color = icap_colors.get(seg["icap"], GREEN)
        add_rect(s, 0.5, 1.6, 2.2, 0.55, ic_color)
        add_text(s, seg["icap"].upper(), 0.5, 1.63, 2.2, 0.5, size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s, f"Topic: {topic}", 0.5, 2.4, 12, 0.55, size=18, bold=True, color=GREEN)
        add_text(s, f"Use {style.lower()} approach. Focus on helping {level.lower()}-level students engage with this segment.", 0.5, 3.1, 12, 1.0, size=15, color=DARK)
        add_text(s, "Instructor Notes:", 0.5, 4.5, 3, 0.4, size=13, bold=True, color=GREEN)
        add_rect(s, 0.5, 5.0, 12.3, 1.8, WHITE)
        add_text(s, "Add your notes here...", 0.7, 5.1, 12, 1.5, size=13, color=RGBColor(0xAA,0xAA,0xAA))

    # ── SLIDE 8: KEY ANALOGIES ───────────────────────────────────────────────
    s8 = prs.slides.add_slide(blank_layout)
    s8.background.fill.solid()
    s8.background.fill.fore_color.rgb = LGRAY
    add_rect(s8, 0, 0, 13.33, 1.3, GREEN)
    add_text(s8, "💡 Key Analogies & Examples", 0.5, 0.2, 12, 0.9, size=28, bold=True, color=WHITE)
    analogies = [
        f'Think of "{topic}" like sorting a messy drawer — you create rules before you touch anything.',
        f'Imagine "{topic}" as a flowchart where each arrow depends on real data you can observe.',
        f'For non-technical students: "{topic}" is like a recipe — ingredients, steps, and a way to check it worked.',
    ]
    for i, a in enumerate(analogies):
        y = 1.5 + i * 1.6
        add_rect(s8, 0.5, y, 0.1, 1.2, ACCENT)
        add_text(s8, a, 0.8, y+0.1, 12.2, 1.1, size=16, color=DARK)

    # ── SLIDE 9: ACTIVITIES ──────────────────────────────────────────────────
    s9 = prs.slides.add_slide(blank_layout)
    s9.background.fill.solid()
    s9.background.fill.fore_color.rgb = LGRAY
    add_rect(s9, 0, 0, 13.33, 1.3, GREEN)
    add_text(s9, "🎯 In-Class Activities", 0.5, 0.2, 12, 0.9, size=28, bold=True, color=WHITE)
    activities = [
        ("Think-Pair-Share", "Interactive",  f'Identify one place where "{topic}" would change the result. Discuss with a partner.'),
        ("Error Spotting",   "Constructive", f'Find the mistake in this incorrect application of "{topic}" and explain why it is wrong.'),
        ("Concept Map",      "Constructive", f'In 5 minutes, sketch how "{topic}" connects to two ideas from previous lectures.'),
    ]
    act_col = {"Interactive":PU,"Constructive":icap_colors["Constructive"]}
    PU = RGBColor(0x6A,0x1A,0x80)
    for i,(title,icap,desc) in enumerate(activities):
        x = 0.4 + i * 4.3
        add_rect(s9, x, 1.5, 4.1, 5.5, WHITE)
        ic_c = icap_colors.get(icap, GREEN)
        add_rect(s9, x, 1.5, 4.1, 0.55, ic_c)
        add_text(s9, title, x+0.1, 1.55, 3.9, 0.45, size=14, bold=True, color=WHITE)
        add_text(s9, icap,  x+0.1, 2.1,  3.9, 0.4,  size=11, color=ic_c)
        add_text(s9, desc,  x+0.1, 2.6,  3.9, 3.5,  size=13, color=DARK)

    # ── SLIDE 10: REFLECTION ─────────────────────────────────────────────────
    s10 = prs.slides.add_slide(blank_layout)
    s10.background.fill.solid()
    s10.background.fill.fore_color.rgb = LGRAY
    add_rect(s10, 0, 0, 13.33, 1.3, GREEN)
    add_text(s10, "🪞 Reflection Questions", 0.5, 0.2, 12, 0.9, size=28, bold=True, color=WHITE)
    reflections = [
        f"What is the single most important idea you learned about \"{topic}\" today?",
        f"Where did you feel confused, and what would help clarify that point?",
        f"How might \"{topic}\" appear in a real project you care about?",
        f"What question would you still like to ask about \"{topic}\"?",
    ]
    for i, r in enumerate(reflections):
        y = 1.5 + i * 1.4
        add_rect(s10, 0.5, y, 0.55, 0.7, GREEN)
        add_text(s10, str(i+1), 0.5, y+0.05, 0.55, 0.6, size=20, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s10, r, 1.3, y+0.1, 11.5, 0.6, size=15, color=DARK)

    # ── SLIDE 11: THANK YOU ──────────────────────────────────────────────────
    s11 = prs.slides.add_slide(blank_layout)
    add_rect(s11, 0, 0, 13.33, 7.5, GREEN)
    add_rect(s11, 0, 5.5, 13.33, 2.0, RGBColor(0x1B,0x43,0x32))
    add_text(s11, "Thank You", 0.5, 1.8, 12, 1.5, size=52, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(s11, f"Any questions about {topic}?", 0.5, 3.4, 12, 0.8, size=22, color=ACCENT, align=PP_ALIGN.CENTER)
    add_text(s11, "Generated by LectureAI · lectureai1-1.onrender.com", 0.5, 5.8, 12, 0.6, size=12, color=RGBColor(0xAA,0xAA,0xAA), align=PP_ALIGN.CENTER)

    # ── SAVE AND RETURN AS DOWNLOAD ──────────────────────────────────────────
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    filename = f"LectureAI_{topic.replace(' ','_')}.pptx"
    return send_file(
        buf,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )

# ── RUN ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True)
```

---

## One extra thing — update your requirements.txt

Add `python-pptx` to it so Render installs it:
```
flask
flask-cors
groq
gunicorn
python-pptx
