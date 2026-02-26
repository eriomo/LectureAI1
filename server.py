from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from groq import Groq
import json
import os

app = Flask(__name__)
CORS(app)

# Use environment variable ONLY
API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=API_KEY)


def ask_groq(prompt, max_tokens=4000):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


# -------------------------------
# FRONTEND ROUTE
# -------------------------------
@app.route("/")
def home():
    return render_template("index.html")


# -------------------------------
# HEALTH CHECK
# -------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running"})


# -------------------------------
# GENERATE LESSON
# -------------------------------
@app.route("/generate", methods=["POST"])
def generate():
    data = request.json

    topic = data.get("topic", "")
    level = data.get("level", "Beginner")
    duration = data.get("duration", 60)
    style = data.get("style", "Standard")

    prompt = f"""
You are an expert educator.

Create a structured lesson plan in STRICT JSON format.

Topic: {topic}
Level: {level}
Duration: {duration} minutes
Style: {style}

Return ONLY valid JSON with this structure:

{{
  "outline": [
    {{
      "title": "string",
      "content": "string",
      "icaps_level": "Passive | Active | Constructive | Interactive"
    }}
  ],
  "activities": [
    {{
      "title": "string",
      "description": "string",
      "icaps_level": "Passive | Active | Constructive | Interactive"
    }}
  ],
  "analogies": ["string"],
  "reflections": ["string"],
  "student": {{
    "micro_explanation": "string",
    "practice_questions": ["string"],
    "srl_prompts": ["string"]
  }}
}}
IMPORTANT:
- Return ONLY JSON.
- No markdown.
- No explanations.
- No text before or after JSON.
"""

    try:
        raw = ask_groq(prompt)

        # Clean possible markdown formatting
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]

        parsed = json.loads(raw)

        return jsonify({
            "success": True,
            "data": parsed
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# -------------------------------
# RUN SERVER
# -------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
