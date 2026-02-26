from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from groq import Groq
import json
import os
import re

app = Flask(__name__)
CORS(app)

API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise ValueError("GROQ_API_KEY not set")

client = Groq(api_key=API_KEY)


def ask_groq(prompt):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=4000,
    )
    return response.choices[0].message.content


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({"status": "running"})


def clean_json(raw):
    raw = raw.strip()

    # remove markdown
    if "```" in raw:
        raw = raw.split("```")[1]

    # extract json object
    start = raw.find("{")
    end = raw.rfind("}") + 1
    raw = raw[start:end]

    # fix invalid escapes
    raw = re.sub(r'\\(?!["\\/bfnrt])', r'\\\\', raw)

    return raw


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.json

        topic = data.get("topic", "")
        level = data.get("level", "Beginner")
        duration = data.get("duration", 60)

        prompt = f"""
Return STRICT JSON only.

Topic: {topic}
Level: {level}
Duration: {duration}

Format:

{{
  "outline": [
    {{
      "title": "string",
      "content": "string"
    }}
  ],
  "activities": [
    {{
      "title": "string",
      "description": "string"
    }}
  ],
  "student": {{
    "micro_explanation": "string",
    "practice_questions": ["string"]
  }}
}}

No text outside JSON.
"""

        raw = ask_groq(prompt)
        cleaned = clean_json(raw)
        parsed = json.loads(cleaned)

        return jsonify({
            "success": True,
            "data": parsed
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
