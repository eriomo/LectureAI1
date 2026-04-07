import os
from flask import Flask, jsonify
from flask_cors import CORS

from routes.classes    import bp as classes_bp
from routes.assignments import bp as assignments_bp
from routes.tests       import bp as tests_bp
from routes.social      import bp as social_bp
from routes.ai          import bp as ai_bp
from routes.library     import bp as library_bp

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# Register blueprints
for bp in [classes_bp, assignments_bp, tests_bp, social_bp, ai_bp, library_bp]:
    app.register_blueprint(bp)


@app.get("/")
def index():
    path = os.path.join(os.path.dirname(__file__), "..", "client", "templates", "index.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


@app.get("/ping")
def ping():
    return jsonify({"status": "ok", "version": "3.0"})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
