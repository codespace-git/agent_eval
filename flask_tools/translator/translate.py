from flask import Flask, request, jsonify
from deep_translator import GoogleTranslator
import random
import uuid

processed_requests = set()

app = Flask(__name__)




@app.route("/translate", methods=["POST"])
def translate():
    data = request.get_json()
    if not data:
        return jsonify({"warning":"no input data found"}),400
    request_id = data.get("request_id", "").strip()
    text = data.get("text","").strip()
    source = data.get("source_language", "auto").strip()
    target = data.get("target_language","english").strip()

    if not request_id:
        return jsonify({"warning": "Missing request identifier"}), 400

    if not text or not target:
        return jsonify({"warning": "Missing text or target language"}), 400

    if request_id in processed_requests:
        return jsonify({"warning": f"Request with identifier {request_id} already processed"}), 200

    processed_requests.add(request_id)
    try:
        translated = GoogleTranslator(source=source, target=target).translate(text)
    except Exception as e:
        return jsonify({"message": f"Translation failed: {str(e)}"}), 500

    return jsonify({
        "source_text": text,
        "translated_text": translated,
        "source_language": source,
        "target_language": target
    }), 200

@app.route("/")
def health(): 
    if random.random()<0.33:
        _ = processed_requests.pop() if processed_requests else None
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006)
