from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from groq import Groq
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app)

API_KEY = os.getenv("GROQ_API_KEY", "")
client = Groq(api_key=API_KEY)

def ask_groq(prompt, max_tokens=4000):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content

# ── Serve the frontend HTML ───────────────────────────────────────────────────
@app.route('/')
def index():
    return send_from_directory('.', 'lectureai_gemini.html')

# ── LAYER 1 & 3: Generate full lesson plan ────────────────────────────────────
@app.route("/generate", methods=["POST"])
def generate():
    data       = request.json
    topic      = data.get("topic", "")
    objectives = data.get("objectives", "")
    level      = data.get("level", "Intermediate")
    duration   = data.get("duration", 75)
    style      = data.get("style", "Lecture-based")

    prompt = f"""You are an expert instructional designer for data science education.
Generate a complete lesson plan AND student support materials using the ICAP framework.

Topic: {topic}
Objectives: {objectives}
Level: {level}
Duration: {duration} minutes
Style: {style}

Return ONLY valid JSON, no markdown, no backticks:
{{
  "outline": [
    {{"segment": "Introduction & Hook",      "duration_min": 10, "icap": "Active",       "description": "2-3 sentences specific to {topic}"}},
    {{"segment": "Core Concept Explanation", "duration_min": 25, "icap": "Passive",      "description": "2-3 sentences specific to {topic}"}},
    {{"segment": "Guided In-Class Activity", "duration_min": 20, "icap": "Constructive", "description": "2-3 sentences specific to {topic}"}},
    {{"segment": "Peer Discussion & Debate", "duration_min": 10, "icap": "Interactive",  "description": "2-3 sentences specific to {topic}"}},
    {{"segment": "Wrap-Up & Reflection",     "duration_min": 10, "icap": "Constructive", "description": "2-3 sentences specific to {topic}"}}
  ],
  "analogies": [
    "Beginner analogy for {topic}: ...",
    "Visual analogy for {topic}: ...",
    "Real-world analogy for {topic}: ..."
  ],
  "activities": [
    {{"title": "Think-Pair-Share", "icap": "Interactive",  "prompt": "specific activity for {topic}"}},
    {{"title": "Error Spotting",   "icap": "Constructive", "prompt": "specific activity for {topic}"}},
    {{"title": "Concept Mapping",  "icap": "Constructive", "prompt": "specific activity for {topic}"}}
  ],
  "reflections": [
    "Reflection question 1 about {topic}",
    "Reflection question 2 about {topic}",
    "Reflection question 3 about {topic}",
    "Reflection question 4 about {topic}"
  ],
  "student": {{
    "micro_explanation": "3 sentences explaining {topic} simply for {level} students with a real-world analogy",
    "practice_questions": [
      {{"difficulty": "Easy",   "question": "easy question about {topic}", "hint": "helpful hint"}},
      {{"difficulty": "Easy",   "question": "easy question about {topic}", "hint": "helpful hint"}},
      {{"difficulty": "Medium", "question": "medium question about {topic}", "hint": "helpful hint"}},
      {{"difficulty": "Medium", "question": "medium question about {topic}", "hint": "helpful hint"}},
      {{"difficulty": "Hard",   "question": "hard question about {topic}", "hint": "helpful hint"}},
      {{"difficulty": "Hard",   "question": "hard question about {topic}", "hint": "helpful hint"}}
    ],
    "srl_prompts": [
      "Before studying {topic}: ...",
      "During study: ...",
      "After practice: ...",
      "Reflection: ..."
    ]
  }}
}}"""

    try:
        raw    = ask_groq(prompt)
        clean  = raw.strip().replace("```json","").replace("```","").strip()
        result = json.loads(clean)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── LAYER 2: Student question ──────────────────────────────────────────────────
@app.route("/layer2/question", methods=["POST"])
def handle_question():
    data     = request.json
    topic    = data.get("topic", "")
    level    = data.get("level", "Intermediate")
    question = data.get("question", "")
    prompt = f"""You are an expert data science instructor helping a teacher respond to a student question live in class.
Current topic: {topic} | Student level: {level}
Student question: "{question}"
Return ONLY valid JSON:
{{"suggested_answer": "2-3 sentences the instructor can say out loud right now",
  "follow_up_question": "One question to ask the class to check understanding",
  "common_misconception": "The likely underlying misconception in one sentence",
  "quick_activity": "A 2-minute activity to reinforce the answer right now"}}"""
    try:
        raw = ask_groq(prompt, 600)
        clean = raw.strip().replace("```json","").replace("```","").strip()
        return jsonify({"success": True, "data": json.loads(clean)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── LAYER 2: Confusion ────────────────────────────────────────────────────────
@app.route("/layer2/confusion", methods=["POST"])
def handle_confusion():
    data      = request.json
    topic     = data.get("topic", "")
    level     = data.get("level", "Intermediate")
    confusion = data.get("confusion", "")
    prompt = f"""You are an expert data science instructor. Students in a live class are confused.
Topic: {topic} | Level: {level}
Confused about: "{confusion}"
Return ONLY valid JSON:
{{"alternative_explanation": "Different explanation using a new analogy, 2-3 sentences",
  "micro_activity": "A 3-minute hands-on activity to deploy RIGHT NOW",
  "visual_suggestion": "Simple diagram the instructor can draw on a whiteboard in 1 minute",
  "reassurance": "One sentence to say to re-engage the class"}}"""
    try:
        raw = ask_groq(prompt, 600)
        clean = raw.strip().replace("```json","").replace("```","").strip()
        return jsonify({"success": True, "data": json.loads(clean)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── LAYER 2: Concept check ────────────────────────────────────────────────────
@app.route("/layer2/conceptcheck", methods=["POST"])
def concept_check():
    data        = request.json
    topic       = data.get("topic", "")
    level       = data.get("level", "Intermediate")
    question    = data.get("question", "")
    correct_pct = data.get("correct_pct", 50)
    prompt = f"""You are an expert data science instructor interpreting live concept check results.
Topic: {topic} | Level: {level}
Question asked: "{question}" | {correct_pct}% answered correctly.
Return ONLY valid JSON:
{{"interpretation": "What these results tell you in one sentence",
  "recommended_action": "Exactly what to do in the next 5 minutes",
  "follow_up_question": "A follow-up to ask the class right now",
  "pace_advice": "Should the instructor move on, slow down, or revisit? One sentence"}}"""
    try:
        raw = ask_groq(prompt, 500)
        clean = raw.strip().replace("```json","").replace("```","").strip()
        return jsonify({"success": True, "data": json.loads(clean)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── LAYER 2: Pacing ───────────────────────────────────────────────────────────
@app.route("/layer2/pacing", methods=["POST"])
def pacing():
    data          = request.json
    topic         = data.get("topic", "")
    total_min     = data.get("total_min", 75)
    elapsed_min   = data.get("elapsed_min", 40)
    current_seg   = data.get("current_segment", "")
    segments_left = data.get("segments_left", [])
    prompt = f"""You are an expert instructor managing live class pacing.
Topic: {topic} | Total: {total_min} min | Elapsed: {elapsed_min} min | Remaining: {total_min - elapsed_min} min
Current segment: "{current_seg}" | Remaining segments: {segments_left}
Return ONLY valid JSON:
{{"status": "on_track or behind or ahead",
  "assessment": "One sentence on where the class stands",
  "recommendation": "What to cut, compress, or expand",
  "must_cover": "The single most important thing to cover before class ends",
  "can_skip": "What can safely be skipped or assigned as self-study"}}"""
    try:
        raw = ask_groq(prompt, 500)
        clean = raw.strip().replace("```json","").replace("```","").strip()
        return jsonify({"success": True, "data": json.loads(clean)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/student", methods=["POST"])
def student():
    return jsonify({"success": True, "data": {"micro_explanation":"","practice_questions":[],"srl_prompts":[]}})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running", "ai": "Groq Llama 3.3", "layers": [1, 2, 3]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🎓 LectureAI running on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
