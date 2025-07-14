from flask import Flask, request, jsonify
import os
from deep_translator import GoogleTranslator
import random


app = Flask(__name__)

try:
    ERROR_PROB = float(os.getenv("ERROR_PROB", "0.1"))
    if not (0.0 <= ERROR_PROB <= 1.0):
        ERROR_PROB = 0.1
except ValueError:
    ERROR_PROB = 0.1


@app.route("/translate", methods=["POST"])
def translate():
    if random.random()<ERROR_PROB:
        return jsonify({"messsage":"internal servor error"}),500

    data = request.get_json()
    if not data:
        return jsonify({"warning":"no input data found"}),400
    text = data.get("text","").strip()
    source = data.get("source_language", "auto").strip()
    target = data.get("target_language","english").strip()

    if not text or not target:
        return jsonify({"warning": "Missing text or target language"}), 400

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
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006)
