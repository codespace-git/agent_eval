from flask import Flask, request, jsonify
import os
import random


app = Flask(__name__)

try:
    ERROR_PROB = float(os.getenv("ERROR_PROB", "0.1"))
    if not (0.0 <= ERROR_PROB <= 1.0):
        ERROR_PROB = 0.1
except ValueError:
    ERROR_PROB = 0.1

def generate_link(query):
    if not query:
        return "https://wiki.com"
    base_keyword = query.split()[0].lower()
    domains = ["learn", "docs", "wiki", "dev", "guide","w3schools", "realpython", "geeksforgeeks", "stackoverflow"]
    tld = random.choice([".com", ".org", ".io", ".dev"])
    return f"https://{base_keyword}.{random.choice(domains)}{tld}/{query.replace(' ', '-')}"

@app.route("/serp", methods=["GET"])
def serp_mock():
    if random.random() < ERROR_PROB :
        return jsonify({"message":"internal server error"}),500
    query = request.args.get("q","").strip()
    
    if not query:
        return jsonify({"warning": "Missing query parameter 'q'"}), 400

    
    mock_results = []
    for i in range(1, random.randint(2, 5)):
        mock_results.append({
            "position": i,
            "title": f"Result {i} for {query}",
            "link": generate_link(query),
            "snippet": f"This is a generated snippet for result {i} related to {query}"
        })

    response = {
        "search_metadata": {
            "id": f"mock-{random.randint(1000, 9999)}",
            "status": "Success"
        },
        "search_parameters": {
            "engine": "google",
            "q": query
        },
        "results": mock_results
    }

    return jsonify(response),200

@app.route("/")
def health():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=5000)
