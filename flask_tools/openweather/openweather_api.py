from flask import Flask, request, jsonify
import random
import time

app = Flask(__name__)

WEATHER_OPTIONS = [
    {"main": "Clear", "description": "clear sky"},
    {"main": "Clouds", "description": "overcast clouds"},
    {"main": "Rain", "description": "light rain"},
    {"main": "Thunderstorm", "description": "stormy skies"},
    {"main": "Snow", "description": "light snow"}
]

@app.route("/weather", methods=["GET"])
   
        
def weather_mock():
    if random.random()<0.1 :
         return jsonify({"status":"error","message":"internal server error"}),500
    city = request.args.get("q", "Unknown City")
    if not city :
        return jsonify({"message":"invalid request"}),400
    global WEATHER_OPTIONS 
    random_weather = random.choice(WEATHER_OPTIONS)
    
    mock_response = {
        "coord": {"longitude": round(random.uniform(-180, 180), 2), "latitude": round(random.uniform(-90, 90), 2)},
        "weather": random_weather,
        "main": {
            "temp": round(random.uniform(280, 310), 2),
            "feels_like": round(random.uniform(275, 305), 2),
            "pressure": random.randint(990, 1025),
            "humidity": random.randint(30, 90)
        },
        "wind": {"speed": round(random.uniform(1, 10), 2), "deg": round(random.randint(0, 360),2)},
        "name": city
    }

    return jsonify(mock_response),200

@app.route("/")
def health():
    return jsonify({"status": "OK"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
