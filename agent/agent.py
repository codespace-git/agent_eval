import os
import json
import random
import logging
import requests
import sqlite3


from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from langchain_openai import OpenAI



os.makedirs("logs", exist_ok=True)

info_logger = logging.getLogger("info")
info_handler = logging.FileHandler("logs/info.log")
info_logger.setLevel(logging.INFO)
info_handler.setFormatter(logging.Formatter("%(asctime)s [agent] %(message)s"))
info_logger.addHandler(info_handler)

agent_logger = logging.getLogger("agent")
agent_handler = logging.FileHandler("logs/agent.log")
agent_logger.setLevel(logging.INFO)
agent_logger.addHandler(agent_handler)


PROXY ={
    "search": "6000",
    "weather":"6001",
    "movie": "6002",
    "calendar": "6003",
    "translator":"6006",
    "calculator":"6004",
    "message": "6005",
}

def call_with_toxic(tool_name, endpoint, method="GET", params=None, json_data=None):
    proxy = PROXY[tool_name]
    url = f"http://toxiproxy:{proxy}{endpoint}"

    try:
        match method:
            case "GET":
                res = requests.get(url, params=params or {}, timeout=5)
            case "POST":
                res = requests.post(url, json=json_data or {}, timeout=5)
            case "DELETE":
                res = requests.delete(url, params=params or {}, timeout=5)
            case _:
                raise ValueError("invalid method")

        res.raise_for_status()
        final = {}
        final["result"]=res.json()
        final["status"] = res.status_code
        return json.dumps(final)


    except ValueError as e:
        info_logger.error(f"{tool_name} failed due to invalid method type: {str(e)}")
        return json.dumps({"result": str(e), "status": 400}, ensure_ascii=False)
    
    except requests.exceptions.Timeout:
        info_logger.error(f"{tool_name} timed out at endpoint {endpoint}")
        return json.dumps({"result": "timeout error","status":408},ensure_ascii=False)

    except requests.exceptions.HTTPError:
        status = getattr(res, "status_code", "unknown")
        info_logger.error(f"{status} {tool_name} error at endpoint {endpoint}")
        return json.dumps({"result": f"HTTP {status} error","status":status},ensure_ascii=False)

    except Exception as e:
        info_logger.error(f"{tool_name} failed: {str(e)}")
        return json.dumps({"result": str(e),"status":500},ensure_ascii=False)

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
        func= lambda d :call_with_toxic("calendar","/events",params={"date":d}),
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
        func=lambda:call_with_toxic("message","/inbox"),
        description="get messages from inbox."
    )
]

def response_handler(agent,prompts,prompt,count):
    try:
        result = agent.run(prompt)
        data = json.loads(result)
        agent_logger.info(json.dumps({
            "prompt": prompt,
            "result": data.get("result", ""),
            "status": data.get("status", 200)
        }, indent=2, ensure_ascii=False))
    except Exception as e:
        agent_logger.error(json.dumps({
            "prompt": prompt,
            "result": str(e),
            "status": "agent_error"
        }, indent=2, ensure_ascii=False))
    finally:
        if count%10==9:
            random.shuffle(prompts)
        if count%10==0:
            with sqlite3.connect("state/state.db")as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE control SET count = -1 WHERE id = 1")
                conn.commit()

if __name__ == "__main__" :
    llm = OpenAI(temperature=0)
    agent = initialize_agent(TOOLS, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=False)

    with open("prompts.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)

    with sqlite3.connect("state/state.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE control SET data_size = ? WHERE id = 1", (len(prompts),))
        conn.commit()

    for i, item in enumerate(prompts):
        count = i+1
        prompt = item.get("prompt")
        with sqlite3.connect("state/state.db") as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE control SET count = ? WHERE id = 1", (count,))
            conn.commit()
        response_handler(agent,prompts,prompt,count)




