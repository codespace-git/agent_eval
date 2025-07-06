from flask import Flask, request, jsonify
from datetime import datetime
import random
import time
import uuid

app = Flask(__name__)


EVENTS = []

def generate_id():
    return str(uuid.uuid4())

@app.route("/events", methods=["GET"])
def list_events():
    if random.random()<0.1 :
        return jsonify({"status":"error","message":"internal server error"}),500
    if random.random() < 0.05:
        time.sleep(10)
    date = request.args.get("date","")
    if date:
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400
        if EVENTS:
            filtered = [e for e in EVENTS if e["date"] == date]
            return jsonify({f"events on date{date}": filtered}), 200
        else:
            return jsonify({"message":"could not find any event","events":[] }), 404
    else:
        return jsonify({"message":"date was undefined"}),400

@app.route("/events", methods=["POST"])

def create_event():
    if random.random()<0.1 :
         return jsonify({"status":"error","message":"internal server error"}),500
    if random.random() < 0.05:
        time.sleep(10)
    data = request.get_json()
    title = data.get("title","")
    date = data.get("date","")
    time = data.get("time", "00:00")

    if not title or not date:
        return jsonify({"error": "Missing required fields: title or date or both"}), 400

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    event = {
        "id": generate_id(),
        "title": title,
        "date": date,
        "time": time
    }
    EVENTS.append(event)
    return jsonify({"message": "Event created", "event": event}), 200

@app.route("/events", methods=["DELETE"])

def delete_event():
    if random.random()<0.1 :
         return jsonify({"status":"error","message":"internal server error"}),500
    if random.random() < 0.05:
        time.sleep(10)
    date = request.get_json().get("date","")
    if not date :
        return jsonify({"status":"error","message":"invalid date entry"}),400
    global EVENTS
    before = len(EVENTS)
    EVENTS = [e for e in EVENTS if e["date"] != date]
    if len(EVENTS) == before:
        return jsonify({"error": "Event not found on specified date"}), 404
    return jsonify({"message": f" all events on date: {date} deleted"}), 200

@app.route("/")
def health():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
