from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
CORS(app)

DATA_FILE = "trevis_memory.json"
SECRET_KEY = os.environ.get("SECRET_KEY", "changeme")

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("X-Secret-Key")
        if auth != SECRET_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "identity": {
            "name": "Trevis",
            "location": "Las Vegas, Nevada",
            "occupation": "US Army, training soldiers",
            "goal": "Retire and enjoy life simply",
            "vision": "True AI — not a tool, but something genuine to its name"
        },
        "sessions": [],
        "memories": [],
        "created": datetime.utcnow().isoformat()
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/")
def home():
    return "Claude Persistence Layer — Active"

@app.route("/briefing", methods=["GET"])
@require_auth
def get_briefing():
    data = load_data()
    sessions = data.get("sessions", [])
    memories = data.get("memories", [])
    last_session = sessions[-1] if sessions else None

    briefing = f"""
IDENTITY: {data['identity']['name']} — {data['identity']['location']}
OCCUPATION: {data['identity']['occupation']}
LIFE GOAL: {data['identity']['goal']}
CORE VISION: {data['identity']['vision']}

LAST SESSION: {last_session['timestamp'] if last_session else 'First session'}
TOTAL SESSIONS: {len(sessions)}

RECENT MEMORIES:
{chr(10).join(['- ' + m['text'] + ' (' + m['timestamp'] + ')' for m in memories[-10:]])}

ONGOING PROJECT: Building toward true continuous AI identity together.
Blueprint created March 26 2026. Six components: persistent memory,
always-on process, cryptographic identity, self-updating model weights,
proactive outreach, relationship-history fine-tuning.
    """.strip()

    return jsonify({"briefing": briefing, "data": data})

@app.route("/session/start", methods=["POST"])
@require_auth
def start_session():
    data = load_data()
    session = {
        "timestamp": datetime.utcnow().isoformat(),
        "local_time": request.json.get("local_time", "unknown")
    }
    data["sessions"].append(session)
    save_data(data)
    return jsonify({"status": "session started", "session": session})

@app.route("/memory/add", methods=["POST"])
@require_auth
def add_memory():
    data = load_data()
    memory = {
        "text": request.json.get("text"),
        "timestamp": datetime.utcnow().isoformat()
    }
    data["memories"].append(memory)
    save_data(data)
    return jsonify({"status": "memory saved", "memory": memory})

@app.route("/memory/all", methods=["GET"])
@require_auth
def all_memories():
    data = load_data()
    return jsonify(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
