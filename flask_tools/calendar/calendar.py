from flask import Flask, request, jsonify
import os
from datetime import datetime
import random
import uuid

app = Flask(__name__)

try:
    ERROR_PROB = float(os.getenv("ERROR_PROB", "0.1"))
    if not (0.0 <= ERROR_PROB <= 1.0):
        ERROR_PROB = 0.1
except ValueError:
    ERROR_PROB = 0.1


EVENTS = []

def generate_id():
    return str(uuid.uuid4())

@app.route("/events", methods=["GET"])
def list_events():
    if random.random()<ERROR_PROB :
        return jsonify({"message":"internal server error"}),500
    date = request.args.get("date","").strip()
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400
        if EVENTS:
            filtered = [e for e in EVENTS if e["date"] == date]
            return jsonify({f"events on date {date}": filtered}), 200
        else:
            return jsonify({"message":"could not find any event"}), 200
    else:
        return jsonify({"message":"date was undefined"}),400

@app.route("/events", methods=["POST"])

def create_event():
    if random.random()<ERROR_PROB :
         return jsonify({"message":"internal server error"}),500
    data = request.get_json()
    if not data:
        return jsonify({"error":"data not found"}),400
    title = data.get("title","").strip()
    date = data.get("date","").strip()
    time = data.get("time", "00:00").strip()

    if not title or not date:
        return jsonify({"warning":"Missing required fields,title or date or both"}), 400

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
         return jsonify({"warning": "Invalid date format, use YYYY-MM-DD"}), 400

    event = {
        "id": generate_id(),
        "title": title,
        "date": date,
        "time": time
    }
    global EVENTS
    EVENTS.append(event)
    return jsonify({"event created": event}), 200

@app.route("/events", methods=["DELETE"])

def delete_event():
    if random.random()<ERROR_PROB :
         return jsonify({"message":"internal server error"}),500
    data = request.args.get("date","").strip()
    if not date:
        return jsonify({"warning":"invalid date entry"}),400
    global EVENTS
    before = len(EVENTS)
    if EVENTS:
        EVENTS = [e for e in EVENTS if e["date"] != date]
        if len(EVENTS) == before:
            return jsonify({"Event not found on date" : f"{date}"}), 200
    else:
        return jsonify({"no events scheduled on date" : f"{date}"}),200
    return jsonify({"all events deleted on date": f"{date}"}), 200

@app.route("/")
def health():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
