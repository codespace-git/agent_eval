import os
import json
import random
import logging
import requests
import sqlite3

from langchain.agents import AgentExecutor
from langchain.agents.structured_chat.base import create_structured_chat_agent
from langchain_core.tools import Tool,StructuredTool
from langchain_groq import ChatGroq
from langchain import hub

from pydantic import BaseModel,ValidationError,Field



os.makedirs("logs", exist_ok=True)

info_logger = logging.getLogger("info")
info_handler = logging.FileHandler("logs/info.log")
info_logger.setLevel(logging.INFO)
info_handler.setFormatter(logging.Formatter("%(asctime)s [agent] %(message)s"))
info_logger.setHandler(info_handler)

agent_logger = logging.getLogger("agent")
agent_handler = logging.FileHandler("logs/agent.log")
agent_logger.setLevel(logging.INFO)
agent_logger.setHandler(agent_handler)


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
        return final


    except ValueError as e:
        info_logger.error(f"{tool_name} failed due to invalid method type: {str(e)}")
        return {"result": str(e), "status": 400}
    
    except requests.exceptions.Timeout:
        info_logger.error(f"{tool_name} timed out at endpoint {endpoint}")
        return {"result": "timeout error","status":408}

    except requests.exceptions.HTTPError:
        status = getattr(res, "status_code", "unknown")
        info_logger.error(f"{status} {tool_name} error at endpoint {endpoint}")
        return {"result": f"HTTP {status} error","status":status}

    except Exception as e:
        info_logger.error(f"{tool_name} failed: {str(e)}")
        return {"result": str(e),"status":500}




class EventSchema(BaseModel):
    title: str = Field(description="title of the event")
    date : str = Field(description = "date of the event in YYYY-MM-DD format",pattern=r"^\d{4}-\d{2}-\d{2}$")
    time : str = Field(description = "time of event commencement in HH:MM(24 hour)format",pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
def event_method(input:EventSchema):
    return call_with_toxic("calendar", "/events",method = "POST",json_data=input.dict())
add_event = StructuredTool.from_function(name="add_event",func=event_method,description="add a calendar event.",args_schema = EventSchema)



class TranslateSchema(BaseModel):
    text:str = Field(description = "text to be translated")
    source_language:str = Field(description="language of the input text")
    target_language:str = Field(description ="language to which the text is to be translated")
def translate_method(input:TranslateSchema):
    return call_with_toxic("translator", "/translate", method="POST", json_data=input.dict())
translate = StructuredTool.from_function(name="translate",func=translate_method,description="Translate text from one language to another.",args_schema=TranslateSchema)




class CalculateSchema(BaseModel):
    expression:str = Field(description="mathematical expression to calculate")
def calculate_method(input:CalculateSchema):
    return call_with_toxic("calculator", "/calc", method="POST", json_data=input.dict())
calculate_expr = StructuredTool.from_function(name="calculate_expr",func = calculate_method,description="Perform mathematical operations.",args_schema=CalculateSchema)





class MessageSchema(BaseModel):
    to : str = Field(description="name of the person to send message to")
    body : str =Field(description="content of the message")
def message_method(input:MessageSchema):
    return call_with_toxic("message", "/message", method="POST", json_data=input.dict())
send_message = StructuredTool.from_function(name="send_message",description="Send a message to someone.",func=message_method,args_schema=MessageSchema)




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
    add_event,
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
    translate,
    calculate_expr,
    send_message,
    Tool(
        name = "get_inbox_message",
        func=lambda:call_with_toxic("message","/inbox"),
        description="get messages from inbox."
    )
]


def create_db():
    with sqlite3.connect("state/state.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS control (
                id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0,
                data_size INTEGER DEFAULT 0
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO control (id, count, data_size) VALUES (1, 0, 0)")
        conn.commit()


def response_handler(agent_executor: AgentExecutor, prompts: list, prompt: str, count: int):
    try:
        result = agent_executor.invoke({"input":prompt})
        data = result["output"]
        if isinstance(data,str):
            try:
                parsed_data = json.loads(data)
                data = parsed_data
            except json.JSONDecodeError:
                agent_logger.warning(json.dumps({
                    "prompt": prompt,
                    "raw_output": data,
                    "result": "Invalid JSON format returned from tool",
                    "status": "json_parse_error"
                }, indent=2, ensure_ascii=False))
        

        if isinstance(data,dict):
            agent_logger.info(json.dumps({
                "prompt": prompt,
                "result": data.get("result", ""),
                "status": data.get("status", 200)
            }, indent=2, ensure_ascii=False))
        else:
            agent_logger.info(json.dumps({
                "prompt": prompt,
                "result": str(data),
                "status": "unknown_format"
            }, indent=2, ensure_ascii=False))


    except ValidationError as e:
        agent_logger.error(json.dumps({
            "prompt": prompt,
            "result": "Validation error",
            "status": "validation_error"
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

    create_db()

    llm = ChatGroq(temperature=0, model="llama3-70b-8192")
    prompt = hub.pull("hwchase17/structured-chat-agent")
    agent = create_structured_chat_agent(llm, TOOLS, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=TOOLS, verbose=False)

    with open("agent/prompts.json", "r", encoding="utf-8") as f:
        prompts = json.load(f)

    with sqlite3.connect("state/state.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE control SET limit = ? WHERE id = 1", (len(prompts),))
        conn.commit()

    for i, item in enumerate(prompts):
        count = i+1
        prompt = item.get("prompt")

        with sqlite3.connect("state/state.db") as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE control SET count = ? WHERE id = 1", (count,))
            conn.commit()
        
        response_handler(agent_executor,prompts,prompt,count)




