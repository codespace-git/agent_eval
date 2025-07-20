from flask import Flask, request, jsonify
import uuid
import random
import time

processed_requests = set()

app = Flask(__name__)


MESSAGES = []

def generate_id():
    return str(uuid.uuid4())

@app.route("/message", methods=["POST"])
def send_message():
    data = request.get_json()
    if not data:
        return jsonify({"warning":"missing data field"}),400
    request_id = data.get("request_id", "").strip()
    recipient = data.get("to", "").strip()
    body = data.get("body", "").strip()

    if not recipient or not body:
        return jsonify({"warning": "Missing 'to' or 'body'"}), 400
    if not request_id:
        return jsonify({"warning": "Missing request identifier"}), 400
    if request_id in processed_requests:
        return jsonify({"warning": f"Request with identifier {request_id} already processed"}), 200
    msg = {
        "id": generate_id(),
        "to": recipient,
        "body": body,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    MESSAGES.append(msg)
    processed_requests.add(request_id)
    return jsonify({"message sent": msg}), 200

@app.route("/inbox", methods=["GET"])
def inbox():
    if random.random()<ERROR_PROB :
         return jsonify({"message":"internal server error"}),500
    if not MESSAGES:
        return jsonify({"messages": "No messages found"}), 200
    return jsonify({"messages": MESSAGES}), 200


@app.route("/")
def health():
    if random.random()<0.33:
        _ = processed_requests.pop() if processed_requests else None
    return jsonify({"status": "OK"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005)
