from flask import Flask, request, jsonify
from flask_cors import CORS
from groq import Groq
import json
import os

app = Flask(__name__)
CORS(app)

# Use environment variable ONLY (no hardcoded key)
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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "running"})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    topic = data.get("topic", "")

    prompt = f"Explain {topic} clearly."

    try:
        raw = ask_groq(prompt)
        return jsonify({"success": True, "data": raw})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# IMPORTANT: Do NOT use fixed port
@app.route("/")
def home():
    return "LectureAI Backend is Running 🚀"
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
