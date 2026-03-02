import os
import re
import json
import io
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

def ask_groq(prompt, max_tokens=1500):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content

def ask_groq_text(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()

def clean_json(raw):
    raw = re.sub(r"```json\s*", "", raw)
    raw = re.sub(r"```\s*", "", raw)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)
    raw = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
    return raw.strip()

@app.route("/")
def index():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "index.html")
    return open(path).read()

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
Generate a complete lesson plan as a JSON object. Return ONLY the JSON, no extra text, no markdown.

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

@app.route("/layer2/question", methods=["POST"])
def layer2_question():
    d        = request.json
    question = d.get("question", "")
    topic    = d.get("topic", "")
    level    = d.get("level", "")

    prompt = f"""
You are an expert data science instructor. A student just asked the following question during a live lecture on "{topic}" for {level}-level students.

Student question: "{question}"

Format your response like this:

WHAT TO SAY:
[2-3 sentences the instructor can say out loud right now]

MISCONCEPTION BEHIND THIS QUESTION:
[1 sentence explaining what the student misunderstood]

FOLLOW-UP FOR THE CLASS:
[1 question to ask the whole class]

QUICK ACTIVITY (2 minutes):
[A simple activity to reinforce the concept right now]
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/layer2/confusion", methods=["POST"])
def layer2_confusion():
    d         = request.json
    confusion = d.get("confusion", "")
    topic     = d.get("topic", "")
    level     = d.get("level", "")

    prompt = f"""
You are an expert data science instructor. During a live lecture on "{topic}" for {level}-level students, the instructor noticed this confusion:

"{confusion}"

Format your response like this:

ALTERNATIVE EXPLANATION:
[Explain the concept in a completely different way using a new analogy]

WHAT TO DRAW ON THE WHITEBOARD:
[A simple diagram the instructor can draw right now]

3-MINUTE RESCUE ACTIVITY:
[A quick activity to fix the confusion]

PHRASE TO RE-ENGAGE THE CLASS:
[One sentence the instructor can say to bring the class back]
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/layer2/conceptcheck", methods=["POST"])
def layer2_conceptcheck():
    d           = request.json
    question    = d.get("question", "")
    correct_pct = d.get("correct_pct", 50)
    topic       = d.get("topic", "")
    level       = d.get("level", "")

    prompt = f"""
You are an expert data science instructor teaching "{topic}" to {level}-level students.
The instructor asked: "{question}"
{correct_pct}% of students answered correctly.

Format your response like this:

WHAT THIS MEANS:
[1-2 sentences on what {correct_pct}% correct tells you]

WHAT TO DO IN THE NEXT 5 MINUTES:
[Specific actions based on the percentage]

FOLLOW-UP QUESTION TO ASK NOW:
[One question to probe deeper]

PACING ADVICE:
[Move on, slow down, or revisit?]
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
Class is {total_duration} minutes total. {mins_elapsed} minutes have passed. {mins_remaining} minutes remain.
Currently on: "{current_segment}"

Format your response like this:

STATUS:
[On track / Behind / Ahead]

WHAT TO DO:
[Specific adjustment to make right now]

MUST COVER BEFORE END:
[The 1-2 most important things that cannot be skipped]

WHAT CAN BE CUT:
[What is safe to skip if needed]
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
You are a friendly data science tutor. A student is asking a question during a lecture on "{topic}".

About this student:
- Name: {name}
- Age: {age}
- Year of study: {year}
- Background: {background}
- Class level: {level}

The student asked: "{question}"

Give a personalised explanation tailored to this student's age, background, and level.
- If they have a non-technical background use everyday analogies
- If they are first year avoid jargon and build from basics
- Keep it friendly, clear, and under 200 words
- End with one encouraging sentence addressed to them by name
- Write like you are talking directly to {name}, no headers or bullet points
"""
    try:
        result = ask_groq_text(prompt)
        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/generate_slides", methods=["POST"])
def generate_slides():
    d          = request.json
    topic      = d.get("topic", "Topic")
    level      = d.get("level", "Intermediate")
    duration   = d.get("duration", 75)
    objectives = d.get("objectives", "")
    style      = d.get("style", "Lecture-based")

    GREEN  = RGBColor(0x2d, 0x6a, 0x4f)
    WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
    DARK   = RGBColor(0x1a, 0x1a, 0x1a)
    LGRAY  = RGBColor(0xF7, 0xF5, 0xF2)
    ACCENT = RGBColor(0x74, 0xC6, 0x9D)

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def add_rect(slide, left, top, width, height, color):
        shape = slide.shapes.add_shape(1, Inches(left), Inches(top), Inches(width), Inches(height))
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        return shape

    def add_text(slide, text, left, top, width, height, size=18, bold=False, color=None, align=PP_ALIGN.LEFT):
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color if color else DARK

    # Slide 1 - Title
    s1 = prs.slides.add_slide(blank)
    add_rect(s1, 0, 0, 13.33, 7.5, GREEN)
    add_rect(s1, 0, 5.8, 13.33, 1.7, RGBColor(0x1B, 0x43, 0x32))
    add_text(s1, "LectureAI", 0.5, 0.5, 12, 0.8, size=14, color=ACCENT, align=PP_ALIGN.CENTER)
    add_text(s1, topic, 0.5, 1.4, 12, 2.0, size=44, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(s1, f"{level} Level  ·  {duration} Minutes  ·  {style}", 0.5, 3.6, 12, 0.7, size=18, color=ACCENT, align=PP_ALIGN.CENTER)

    # Slide 2 - Objectives
    s2 = prs.slides.add_slide(blank)
    s2.background.fill.solid()
    s2.background.fill.fore_color.rgb = LGRAY
    add_rect(s2, 0, 0, 13.33, 1.3, GREEN)
    add_text(s2, "Learning Objectives", 0.5, 0.2, 12, 0.9, size=30, bold=True, color=WHITE)
    obj_lines = objectives.strip().split("\n") if objectives else ["Understand key concepts", "Apply the methods", "Evaluate the results"]
    for i, obj in enumerate(obj_lines[:6]):
        y = 1.6 + i * 0.85
        add_rect(s2, 0.5, y, 0.45, 0.6, GREEN)
        add_text(s2, str(i+1), 0.5, y+0.05, 0.45, 0.5, size=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s2, obj.lstrip("0123456789. "), 1.2, y+0.08, 11.5, 0.55, size=16, color=DARK)

    # Slides 3-7 - One per segment
    segments = [
        {"name": "Introduction & Hook",      "icap": "Active",       "pct": 0.12},
        {"name": "Core Concept Explanation",  "icap": "Passive",      "pct": 0.35},
        {"name": "Guided In-Class Activity",  "icap": "Constructive", "pct": 0.28},
        {"name": "Peer Discussion & Debate",  "icap": "Interactive",  "pct": 0.13},
        {"name": "Wrap-Up & Reflection",      "icap": "Constructive", "pct": 0.12},
    ]
    icap_colors = {
        "Passive":      RGBColor(0xC0, 0x44, 0x0A),
        "Active":       RGBColor(0x1A, 0x66, 0x40),
        "Constructive": RGBColor(0x1A, 0x3F, 0x80),
        "Interactive":  RGBColor(0x6A, 0x1A, 0x80),
    }
    for i, seg in enumerate(segments):
        s = prs.slides.add_slide(blank)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = LGRAY
        add_rect(s, 0, 0, 13.33, 1.3, GREEN)
        add_text(s, f"Segment {i+1}", 0.5, 0.05, 4, 0.4, size=11, color=ACCENT)
        add_text(s, seg["name"], 0.5, 0.4, 10, 0.8, size=26, bold=True, color=WHITE)
        mins = max(5, round(duration * seg["pct"]))
        add_text(s, f"{mins} min", 10.5, 0.4, 2.5, 0.7, size=20, bold=True, color=ACCENT, align=PP_ALIGN.RIGHT)
        ic = icap_colors.get(seg["icap"], GREEN)
        add_rect(s, 0.5, 1.6, 2.2, 0.5, ic)
        add_text(s, seg["icap"].upper(), 0.5, 1.63, 2.2, 0.45, size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s, f"Topic: {topic}", 0.5, 2.4, 12, 0.5, size=18, bold=True, color=GREEN)
        add_text(s, f"Use {style.lower()} approach for {level.lower()}-level students.", 0.5, 3.1, 12, 0.6, size=15, color=DARK)
        add_rect(s, 0.5, 5.0, 12.3, 1.8, WHITE)
        add_text(s, "Instructor notes...", 0.7, 5.1, 12, 1.5, size=13, color=RGBColor(0xAA, 0xAA, 0xAA))

    # Slide 8 - Thank You
    s8 = prs.slides.add_slide(blank)
    add_rect(s8, 0, 0, 13.33, 7.5, GREEN)
    add_rect(s8, 0, 5.5, 13.33, 2.0, RGBColor(0x1B, 0x43, 0x32))
    add_text(s8, "Thank You", 0.5, 2.0, 12, 1.5, size=52, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(s8, f"Any questions about {topic}?", 0.5, 3.6, 12, 0.8, size=22, color=ACCENT, align=PP_ALIGN.CENTER)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    filename = f"LectureAI_{topic.replace(' ', '_')}.pptx"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation")

if __name__ == "__main__":
    app.run(debug=True)
