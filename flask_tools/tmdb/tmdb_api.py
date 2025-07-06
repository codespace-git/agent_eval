from flask import Flask, request, jsonify
import random
import json
import time

app = Flask(__name__)

with open("movies.json", "r") as f :
    MOVIES = json.load(f)


@app.route("/movie", methods=["GET"])
def search_movie():
    if random.random() < 0.1:
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500
    response = request.args
    query = response.get("query","")
    language = response.get("language", "en")
    page = int(response.get("page", 1))
    per_page = int(response.get("per_page", 2))  

    if not query or not isinstance(query,str):
        return jsonify({"status": "fail","message": "Missing required parameter: query"}), 400

   
    filtered = [
        movie for movie in MOVIES
        if query.lower() in movie["name"].lower() and query.lower() in movie["original_name"].lower()
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