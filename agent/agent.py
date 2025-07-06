import os
import json
import random
import logging
import requests


from flask import jsonify

from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain_community.llms import OpenAI


from proxy_n_toxic.corrupt_request import add_toxic, remove_toxic

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/agent.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


TOXIC_PROB = 0.01
PROXY={
    "search":{"proxy":"search_proxy",
               "url":"6000" },
    "weather":{"proxy":"weather_proxy",
                "url":"6001"},
    "movie":{"proxy":"movie_proxy",
             "url":"6002"},
    "calendar":{"proxy":"calendar_proxy",
                "url":"6003"},
    "translator":{"proxy":"translator_proxy",
                 "url":"6006"},
    "calculator":{"proxy":"calculator_proxy",
                 "url":"6004"},
    "message":{"proxy":"message_proxy",
              "url":"6005"}
}



def call_with_toxic(tool_name, endpoint, method="GET", params=None, json_data=None):
    proxy = PROXY[tool_name]
    url = f"http://toxiproxy:{proxy["url"]}{endpoint}"
    injected = False

    if random.random() < TOXIC_PROB:
        logging.info(f"Injecting toxic for {tool_name}")
        add_toxic(proxy["proxy"])
        injected = True

    try:
        if method == "GET":
            res = requests.get(url, params=params, timeout=5)
        elif method == "POST":
            res = requests.post(url, json=json_data, timeout=5)
        elif method == "DELETE":
            res = requests.delete(url, params=params, timeout=5)
        else:
            raise ValueError("invalid method")
        res.raise_for_status()
        return res.json()

    except requests.exceptions.Timeout:
        logging.error(f" {tool_name} timed out at endpoint {endpoint}")
        return jsonify({"error": "Timeout"})

    except requests.exceptions.HTTPError as e:
        logging.error(f" {res.status_code} {tool_name} error at endpoint {endpoint}")
        return jsonify({"error": f"HTTP {res.status_code}"})

    except Exception as e:
        logging.error(f" {tool_name} failed: {str(e)}")
        return jsonify({"error": str(e)})

    finally:
        if injected:
            remove_toxic(proxy["proxy"])
            logging.info(f"Removed toxic for {tool_name}")
            injected = False


TOOLS = [
    Tool(
        name="search_web",
        func=lambda q: call_with_toxic("search", "/serp", params={"q": q}),
        description="Search the internet for information."
    ),
    Tool(
        name="get_weather",
        func=lambda city: call_with_toxic("weather", "/weather", params={"q": city}),
        description="Get current weather for a city."
    ),
    Tool(
        name="search_movie",
        func=lambda title: call_with_toxic("movie", "/movie", params={"query": title}),
        description="Search for a movie."
    ),
    Tool(
        name="add_event",
        func=lambda d: call_with_toxic("calendar", "/events", method="POST", json_data=d),
        description="Add an event on calendar."
    ),
    Tool(
        name="delete_event_by_date",
        func=lambda d: call_with_toxic("calendar", "/events", method="DELETE", params={"date": d}),
        description="Delete all events on a date."
    ),
    Tool(
        name="get_event",
        func= lambda d :call_with_toxic("calendar","/events",method ="GET",params={"date":d}),
        description="get all events on a calendar date."
    ),
    Tool(
        name="translate",
        func=lambda payload: call_with_toxic("translator", "/translate", method="POST", json_data=payload),
        description="Translate text from one language to another."
    ),
    Tool(
        name="calculate_expr",
        func=lambda expr: call_with_toxic("calculator", "/calc", method="POST", json_data={"expr": expr}),
        description="Perform mathematical operations."
    ),
    Tool(
        name="send_message",
        func=lambda body: call_with_toxic("message", "/message", method="POST", json_data=body),
        description="Send a message to someone."
    ),
    Tool(
        name = "get_inbox_message",
        func=lambda:call_with_toxic("message","/inbox",method = "GET"),
        description="get messages from inbox."
    )
]

llm = OpenAI(temperature=0)
agent = initialize_agent(TOOLS, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=False)

with open("agent/prompts.json", "r", encoding="utf-8") as f:
    prompts = json.load(f)

for i, item in enumerate(prompts):
    prompt = item.get("prompt")
    logging.info(f"\n[Prompt {i+1}] {prompt}")
    print(f"\n[Prompt {i+1}] {prompt}")
    try:
        result = agent.run(prompt)
        logging.info(json.dumps({
                "prompt":prompt,
                "result":result
            },ensure_ascii=False))
    except Exception as e:
        logging.error(json.dumps({"prompt":prompt,
                "error":str(e)},ensure_ascii=False))





