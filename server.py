from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import json, os, re

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("GROQ_API_KEY", "")
client = Groq(api_key=API_KEY)

def clean_json(raw):
    raw = raw.strip()
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'^```\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        raw = match.group(0)
    raw = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
    return raw

def ask_groq(prompt, max_tokens=4000):
    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=max_tokens
    )
    return r.choices[0].message.content

def safe_lesson(topic):
    return {
        "outline": [
            {"segment": "Introduction & Hook",      "duration_min": 10, "icap": "Active",       "description": f"Open with a compelling real-world application of {topic}."},
            {"segment": "Core Concept Explanation", "duration_min": 25, "icap": "Passive",      "description": f"Explain the core principles of {topic} with visual examples."},
            {"segment": "Guided In-Class Activity", "duration_min": 20, "icap": "Constructive", "description": f"Students apply {topic} to a structured hands-on problem."},
            {"segment": "Peer Discussion & Debate", "duration_min": 10, "icap": "Interactive",  "description": f"Groups compare approaches and defend reasoning about {topic}."},
            {"segment": "Wrap-Up & Reflection",     "duration_min": 10, "icap": "Constructive", "description": f"Exit ticket: students write the most important idea from {topic}."}
        ],
        "analogies": [
            f"Beginner analogy: Think of {topic} like sorting items into labelled boxes.",
            f"Visual analogy: {topic} is like a flowchart where each branch depends on your data.",
            f"Real-world analogy: {topic} appears in recommendation systems and fraud detection every day."
        ],
        "activities": [
            {"title": "Think-Pair-Share", "icap": "Interactive",  "prompt": f"Apply {topic} to a sample dataset and compare results with a partner."},
            {"title": "Error Spotting",   "icap": "Constructive", "prompt": f"Find the mistake in this incorrect application of {topic}."},
            {"title": "Concept Mapping",  "icap": "Constructive", "prompt": f"Map how {topic} connects to at least two other concepts you know."}
        ],
        "reflections": [
            f"What is the single most important idea you learned about {topic} today?",
            f"Where did you feel confused about {topic}, and what would help clarify it?",
            f"How might {topic} appear in a real dataset or project you care about?",
            f"What question would you still like to ask about {topic}?"
        ],
        "student": {
            "micro_explanation": f"{topic} is a systematic method for extracting insight from data. Think of it as a recipe: the right ingredients (data), the right steps (method), and a way to check the result (evaluation).",
            "practice_questions": [
                {"difficulty": "Easy",   "question": f"In one sentence, define {topic} in your own words.", "hint": "Focus on what it does, not how it works."},
                {"difficulty": "Easy",   "question": f"Give one real-life example where {topic} would be useful.", "hint": "Think about everyday decisions that rely on data patterns."},
                {"difficulty": "Medium", "question": f"Explain one advantage and one limitation of {topic}.", "hint": "Consider what assumptions it makes about data."},
                {"difficulty": "Medium", "question": f"How would you explain {topic} to a friend who has never studied data science?", "hint": "Use an analogy from everyday life."},
                {"difficulty": "Hard",   "question": f"Design a small experiment to test whether {topic} performs well on a dataset of your choice. What metrics would you use?", "hint": "Think about what success means for your specific problem."},
                {"difficulty": "Hard",   "question": f"What ethical concerns might arise when applying {topic} in healthcare or hiring?", "hint": "Consider bias, transparency, and accountability."}
            ],
            "srl_prompts": [
                f"Before studying {topic}: What do I already know about this?",
                f"During study: Am I understanding {topic} or just reading the words?",
                f"After practice: Can I explain {topic} without looking at my notes?",
                "Reflection: What is my plan for the parts I found difficult?"
            ]
        }
    }

@app.route("/")
def index():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lectureai_gemini.html")
    with open(path, encoding="utf-8") as f:
        return f.read(), 200, {"Content-Type": "text/html"}

@app.route("/generate", methods=["POST"])
def generate():
    d          = request.json or {}
    topic      = d.get("topic", "Data Science")
    objectives = d.get("objectives", "")
    level      = d.get("level", "Intermediate")
    duration   = d.get("duration", 75)
    style      = d.get("style", "Lecture-based")

    prompt = f"""You are an expert instructional designer for data science education.
Generate a lesson plan using the ICAP framework for:
Topic: {topic} | Level: {level} | Duration: {duration}min | Style: {style}
Objectives: {objectives}

Return ONLY a raw JSON object. No markdown. No backticks. No explanation. Just JSON:
{{
  "outline": [
    {{"segment":"Introduction & Hook","duration_min":10,"icap":"Active","description":"specific hook for {topic}"}},
    {{"segment":"Core Concept Explanation","duration_min":25,"icap":"Passive","description":"explain {topic} clearly"}},
    {{"segment":"Guided In-Class Activity","duration_min":20,"icap":"Constructive","description":"hands-on {topic} task"}},
    {{"segment":"Peer Discussion & Debate","duration_min":10,"icap":"Interactive","description":"debate about {topic}"}},
    {{"segment":"Wrap-Up & Reflection","duration_min":10,"icap":"Constructive","description":"exit ticket for {topic}"}}
  ],
  "analogies": [
    "Beginner analogy about {topic}",
    "Visual analogy about {topic}",
    "Real-world analogy about {topic}"
  ],
  "activities": [
    {{"title":"Think-Pair-Share","icap":"Interactive","prompt":"activity about {topic}"}},
    {{"title":"Error Spotting","icap":"Constructive","prompt":"error activity about {topic}"}},
    {{"title":"Concept Mapping","icap":"Constructive","prompt":"mapping activity about {topic}"}}
  ],
  "reflections": [
    "reflection 1 about {topic}",
    "reflection 2 about {topic}",
    "reflection 3 about {topic}",
    "reflection 4 about {topic}"
  ],
  "student": {{
    "micro_explanation": "3 sentence plain explanation of {topic} for {level} students",
    "practice_questions": [
      {{"difficulty":"Easy","question":"easy question about {topic}","hint":"helpful hint"}},
      {{"difficulty":"Easy","question":"easy question about {topic}","hint":"helpful hint"}},
      {{"difficulty":"Medium","question":"medium question about {topic}","hint":"helpful hint"}},
      {{"difficulty":"Medium","question":"medium question about {topic}","hint":"helpful hint"}},
      {{"difficulty":"Hard","question":"hard question about {topic}","hint":"helpful hint"}},
      {{"difficulty":"Hard","question":"hard question about {topic}","hint":"helpful hint"}}
    ],
    "srl_prompts": [
      "before studying prompt",
      "during study prompt",
      "after practice prompt",
      "reflection prompt"
    ]
  }}
}}"""

    try:
        raw    = ask_groq(prompt)
        clean  = clean_json(raw)
        result = json.loads(clean)
        if not isinstance(result.get("outline"), list):
            raise ValueError("outline missing")
        if not isinstance(result.get("student"), dict):
            raise ValueError("student missing")
        return jsonify({"success": True, "data": result})
    except Exception:
        return jsonify({"success": True, "data": safe_lesson(topic), "fallback": True})

@app.route("/layer2/question", methods=["POST"])
def layer2_question():
    d = request.json or {}
    p = f"""Expert data science instructor. Topic: {d.get('topic','')}, Level: {d.get('level','Intermediate')}.
Student question: "{d.get('question','')}"
Return ONLY raw JSON:
{{"suggested_answer":"2-3 sentences to say out loud now","follow_up_question":"one question for the class","common_misconception":"likely misconception in one sentence","quick_activity":"2-minute activity to reinforce"}}"""
    try:
        return jsonify({"success": True, "data": json.loads(clean_json(ask_groq(p, 600)))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/layer2/confusion", methods=["POST"])
def layer2_confusion():
    d = request.json or {}
    p = f"""Expert instructor. Topic: {d.get('topic','')}, Level: {d.get('level','')}.
Students confused about: "{d.get('confusion','')}"
Return ONLY raw JSON:
{{"alternative_explanation":"new analogy 2-3 sentences","micro_activity":"3-min activity now","visual_suggestion":"whiteboard diagram description","reassurance":"one sentence to re-engage class"}}"""
    try:
        return jsonify({"success": True, "data": json.loads(clean_json(ask_groq(p, 600)))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/layer2/conceptcheck", methods=["POST"])
def layer2_check():
    d = request.json or {}
    p = f"""Expert instructor. Topic: {d.get('topic','')}, {d.get('correct_pct',50)}% answered "{d.get('question','')}" correctly.
Return ONLY raw JSON:
{{"interpretation":"what results mean in one sentence","recommended_action":"what to do in next 5 minutes","follow_up_question":"ask class this right now","pace_advice":"move on slow down or revisit"}}"""
    try:
        return jsonify({"success": True, "data": json.loads(clean_json(ask_groq(p, 500)))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/layer2/pacing", methods=["POST"])
def layer2_pacing():
    d = request.json or {}
    p = f"""Expert instructor. Topic: {d.get('topic','')}, {d.get('elapsed_min',0)}/{d.get('total_min',75)}min elapsed. On: "{d.get('current_segment','')}". Remaining: {d.get('segments_left',[])}.
Return ONLY raw JSON:
{{"status":"on_track or behind or ahead","assessment":"one sentence on time","recommendation":"what to adjust","must_cover":"most important thing to cover","can_skip":"what to skip"}}"""
    try:
        return jsonify({"success": True, "data": json.loads(clean_json(ask_groq(p, 500)))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/student", methods=["POST"])
def student():
    return jsonify({"success": True, "data": {"micro_explanation": "", "practice_questions": [], "srl_prompts": []}})

@app.route("/health")
def health():
    return jsonify({"status": "running", "ai": "Groq Llama 3.3", "layers": [1, 2, 3]})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"LectureAI running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
