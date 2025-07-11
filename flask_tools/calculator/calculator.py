from flask import Flask, request, jsonify
import math
import random
import time

app = Flask(__name__)

@app.route("/calc", methods=["POST"])
def calculator():
    if random.random() < 0.1:
        return jsonify({"error":"server internal error"}),500
    
    data = request.get_json()
    if not data:
        return jsonify({"error":"data not found"}),400
    expr = data.get("expression", "").strip()

    if not expr:
        return jsonify({"error": "Missing expression field"}), 400

    try:
        allowed_names = {
            k: v for k, v in math.__dict__.items() if not k.startswith("__")
        }
        allowed_names["abs"] = abs
        allowed_names["round"] = round

        result = eval(expr, {"__builtins__": {}}, allowed_names)

        if math.isinf(result) or math.isnan(result):
            raise ValueError("Invalid result")

        return jsonify({"result": result}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def health():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5004)
