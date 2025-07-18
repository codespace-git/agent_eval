from flask import Flask, request, jsonify
from deep_translator import GoogleTranslator
import random
import time

app = Flask(__name__)

@app.route("/translate", methods=["POST"])
def translate():
    if random.random()<0.1:
        return jsonify({"error":"internal servor error"}),500

    data = request.get_json()
    if not data:
        return jsonify({"error":"no data found"}),400
    text = data.get("text","")
    source = data.get("source_language", "auto")
    target = data.get("target_language","english")

    if not text or not target:
        return jsonify({"error": "Missing text or target language"}), 404

    try:
        translated = GoogleTranslator(source=source, target=target).translate(text)
    except Exception as e:
        return jsonify({"error": f"Translation failed: {str(e)}"}), 500

    return jsonify({
        "translated_text": translated,
        "source_language": source,
        "target_language": target
    }), 200

@app.route("/")
def health():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5006)
