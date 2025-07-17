from flask import Flask, request, jsonify
import os
import random
import json


app = Flask(__name__)

try:
    ERROR_PROB = float(os.getenv("ERROR_PROB", "0.1"))
    if not (0.0 <= ERROR_PROB <= 1.0):
        ERROR_PROB = 0.1
except ValueError:
    ERROR_PROB = 0.1

MOVIES = []

@app.route("/movie", methods=["GET"])
def search_movie():
    if random.random() < ERROR_PROB:
        return jsonify({"message": "Internal Server Error"}), 500
    response = request.args
    query = response.get("query","").strip()
    language = response.get("language", "en").strip()
    page = int(response.get("page", 1))
    per_page = int(response.get("per_page", 2))  

    if not query :
        return jsonify({"warning": "Missing required parameter: query"}), 400
    
    
    try:
        with open("movies.json", "r") as f:
            MOVIES = json.load(f)
    except FileNotFoundError:
        return jsonify({"message": "Movies data not available"}), 200
    except json.JSONDecodeError:
        return jsonify({"message": "Error decoding movies data"}), 500
    if not MOVIES:
        return jsonify({"message": "No movies list found"}), 200
    global MOVIES
    filtered = [
        movie for movie in MOVIES
        if query.lower() in movie.get("name","").lower() or query.lower() in movie.get("original_name","").lower()
    ]

   
    start = (page - 1) * per_page
    end = start + per_page
    results = filtered[start:end]

    return jsonify({
        "page": page,
        "per_page": per_page,
        "total_results": len(filtered),
        "results": results
    }),200

@app.route("/")
def health_check():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)