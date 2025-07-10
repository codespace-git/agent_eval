from flask import Flask, request, jsonify
import os
import uuid
import random
import time

app = Flask(__name__)

try:
    ERROR_PROB = float(os.getenv("ERROR_PROB", "0.1"))
    if not (0.0 <= ERROR_PROB <= 1.0):
        ERROR_PROB = 0.1
except ValueError:
    ERROR_PROB = 0.1


MESSAGES = []

def generate_id():
    return str(uuid.uuid4())

@app.route("/message", methods=["POST"])
def send_message():
    if random.random()<ERROR_PROB :
         return jsonify({"status":"error","message":"internal server error"}),500
    data = request.get_json()
    if not data:
        return jsonify({"error:missing data field"}),400
    recipient = data.get("to", "").strip()
    body = data.get("body", "").strip()

    if not recipient or not body:
        return jsonify({"error": "Missing 'to' or 'body'"}), 400

    msg = {
        "id": generate_id(),
        "send-to": recipient,
        "body": body,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    global MESSAGES
    MESSAGES.append(msg)
    return jsonify({"status": "sent", "message": msg}), 200

@app.route("/inbox", methods=["GET"])
def inbox():
    if random.random()<ERROR_PROB :
         return jsonify({"status":"error","message":"internal server error"}),500
    return jsonify({"messages": MESSAGES}), 200


@app.route("/")
def health():
    return jsonify({"status": "OK"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
