import os
import json
import random
import re
import uuid
import logging
import requests
import sqlite3

from langchain.agents import AgentExecutor
from langchain.agents.structured_chat.base import create_structured_chat_agent
from langchain_core.tools import Tool,StructuredTool
from langchain_groq import ChatGroq
from langchain import hub

from dbmanager import AgentDataBaseManager
from datetime import datetime
from pydantic import BaseModel,ValidationError,Field


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

class ToolLimitReachedException(Exception):
    def __init__(self, status_code,start_time,end_time,message):
        self.status_code = status_code
        self.start_time = start_time
        self.end_time = end_time
        self.message = message
        super().__init__(message)

def call_with_toxic(tool_name, endpoint, method="GET", params=None, json_data=None):
    proxy = PROXY[tool_name]
    url = f"http://toxiproxy:{proxy}{endpoint}"
    tool_attempts = 0
    db_manager = AgentDatabaseManager("state/state.db","network.db")
    row = db_manager.get_network_state()
    
    if row:
        tool_limit, prompt_limit,prompt_attempt,prob,start = row
        if not start:
            start = datetime.now().isoformat()
            db_manager.update_network_start(start)
    else:
        tool_limit, prompt_limit,prompt_attempt,prob, start = 1, 1 ,0, 0.1,datetime.now().isoformat()

    while tool_attempts < tool_limit:
        try:
                 
            if method == "GET":
                res = requests.get(url, params=params or {}, timeout=5)
            elif method == "POST":
                res = requests.post(url, json=json_data or {}, timeout=5)
            elif method == "DELETE":
                res = requests.delete(url, params=params or {}, timeout=5)

            network_end = datetime.now()
            network_start = datetime.fromisoformat(start)
            network_latency = (network_end - network_start).total_seconds()
            total_attempts = (tool_limit*prompt_attempt)+tool_attempts + 1

            info_logger.info(json.dumps({
                "tool":tool_name,
                "network_start":start,
                "network_end":network_end.isoformat(),
                "network_latency": network_latency,
                "total_tool_attempts": total_attempts
            },indent=2,ensure_ascii = False))
   
            final = {
            "result": res.json(),
            "status": res.status_code
            }

            return final
                
        except (requests.exceptions.Timeout,requests.exceptions.ConnectionError) as e:
            tool_attempts += 1
            
            if tool_attempts >= tool_limit:
                return {"result": "Tool limit exceeded", "status": 600}

            if isinstance(e, requests.exceptions.Timeout):
                info_logger.error(f"{tool_name} timed out at endpoint {endpoint} after {tool_attempts} tool attempts in {prompt_attempt} prompt attempts")
            elif isinstance(e,requests.exceptions.ConnectionError):
                info_logger.error(f"Connection aborted with {tool_name} at endpoint {endpoint} after {tool_attempts} tool attempts in {prompt_attempt} prompt attempts")

            db_manager.update_control_inject(int(random.random() < prob))
            continue
                
        except Exception as e:
            info_logger.error(f"{tool_name} failed: {str(e)}")
            return {"result": str(e),"status":500}
        
        



class EventSchema(BaseModel):
    title: str = Field(description="title of the event")
    date : str = Field(description = "date of the event in YYYY-MM-DD format",pattern=r"^\d{4}-\d{2}-\d{2}$")
    time : str = Field(description = "time of event commencement in HH:MM(24 hour)format",pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    request_id : str = Field(default_factory=lambda: str(uuid.uuid4()), description="unique identifier for the request")
def event_method(input:EventSchema):
    return call_with_toxic("calendar", "/events",method = "POST",json_data=input.dict())
add_event = StructuredTool.from_function(name="add_event",func=event_method,description="add a calendar event.",args_schema = EventSchema)



class TranslateSchema(BaseModel):
    text:str = Field(description = "text to be translated")
    source_language:str = Field(description="language of the input text")
    target_language:str = Field(description ="language to which the text is to be translated")
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="unique identifier for the request")
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
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="unique identifier for the request")
def message_method(input:MessageSchema):
    return call_with_toxic("message", "/message", method="POST", json_data=input.dict())
send_message = StructuredTool.from_function(name="send_message",description="Send a message to someone.",func=message_method,args_schema=MessageSchema)



class SearchMovieSchema(BaseModel):
    query: str = Field(description="name of the movie to search for")
    language: str = Field(default="en", description="language of the movie")
    page: int = Field(default=1, ge=1, description="page number for pagination")
    per_page: int = Field(default=2, ge=1, description="number of results per page")
def search_movie_method(input: SearchMovieSchema):
    return call_with_toxic("movie", "/movie", params=input.dict())
search_movie = StructuredTool.from_function(name="search_movie",func=search_movie_method,description="Search for a movie.",args_schema=SearchMovieSchema)


TOOLS = [
    Tool(
        name="search_web",
        func=lambda query: call_with_toxic("search", "/serp", params={"q": query}),
        description="Search the internet for information."
    ),
    Tool(
        name="get_weather",
        func=lambda city: call_with_toxic("weather", "/weather", params={"q": city}),
        description="Get current weather for a city."
    ),
    search_movie,
    add_event,
    Tool(
        name="delete_event_by_date",
        func=lambda date: call_with_toxic("calendar", "/events", method="DELETE", params={"date": date, "request_id": str(uuid.uuid4())}),
        description="Delete all events on a date,use and send unique request id."
    ),
    Tool(
        name="get_event",
        func= lambda date :call_with_toxic("calendar","/events",params={"date":date}),
        description="Get all events on a calendar date."
    ),
    translate,
    calculate_expr,
    send_message,
    Tool(
        name = "get_inbox_message",
        func=lambda:call_with_toxic("message","/inbox"),
        description="Get messages from inbox."
    )
]


def create_dbs(db_manager:AgentDataBaseManager):
    os.makedirs("state", exist_ok=True)
    os.makedirs("network",exist_ok = True)
    db_manager._init_dbs()

def classifier(status:int):
        if 400<=status<500 :
            return "agent"
        elif 500<=status<600 :
            return "server"
        else :
            return "none"

def error_classifier(status):
    if isinstance(status,int):
        return classifier(status)
    else:
        match = re.search(r'["\']?status["\']\s*:\s*(\d+)', str(status))
        if match:
            status_code= int(match.group(1))
            error_type = classifier(status_code)
            return error_type,status_code
        else:
            return "could not resolve error type",599
    

def log_agent_response(log_level, prompt, response, status, start_time, end_time, duration, error_type, attempt_no):
    log_data = {
        "prompt": prompt,
        "response": response,
        "status": status,
        "start_time": start_time.isoformat() if start_time else "",
        "end_time": end_time.isoformat() if end_time else "",
        "duration": duration,
        "error_type": error_type,
        "prompt_attempt_no": attempt_no
    }
    log_message = json.dumps(log_data, indent=2, ensure_ascii=False)

    if log_level == logging.INFO:
        agent_logger.info(log_message)
    elif log_level == logging.WARNING:
        agent_logger.warning(log_message)
    elif log_level == logging.ERROR:
        agent_logger.error(log_message)


def response_handler(agent_executor: AgentExecutor, prompt: str, prob:float,db_manager:AgentDatabaseManager):
    state = True
    row = db_manager.get_network_state()
    if row:
        attempt_no = row[2] + 1
    else:
        attempt_no = 1

    prompt_start = datetime.now()
    
    try:
        result = agent_executor.invoke({"input":prompt})
        prompt_end = datetime.now()
        duration = (prompt_end - prompt_start).total_seconds()
        data = result.get("output")
        
        if isinstance(data,str):
            try:
                parsed_data = json.loads(data)
                status = parsed_data.get("status")
                if status == 600:
                    raise ToolLimitReachedException(600,prompt_start,prompt_end,"tool limit reached for prompt attempt "+str(attempt_no))
                if 400<=status<600:
                    state=False
                log_agent_response(logging.INFO, prompt, parsed_data.get("result"), status, prompt_start, prompt_end, duration, error_classifier(status), attempt_no)

            except json.JSONDecodeError:
                error_type,status = error_classifier(data)
                if status == 600:
                    raise ToolLimitReachedException(600,prompt_start,prompt_end,"tool limit reached for prompt attempt "+str(attempt_no))
                if 400<=status<600:
                    state = False
                log_agent_response(logging.WARNING,prompt, data, status, prompt_start, prompt_end, duration, error_type, attempt_no)
        

        elif isinstance(data,dict):
            status = data.get("status")
            if status == 600:
                raise ToolLimitReachedException(600,prompt_start,prompt_end,"tool limit reached for prompt attempt "+str(attempt_no))
            if 400<=status<600 :
                state=False
            log_agent_response(logging.INFO, prompt, data.get("result"), status, prompt_start, prompt_end, duration, error_classifier(status), attempt_no)
        
        else:
            text = str(data)
            error_type,status = error_classifier(text)
            if status == 600:
                raise ToolLimitReachedException(600,prompt_start,prompt_end,"tool limit reached for prompt attempt "+str(attempt_no))
            if 400<=status<600:
                state = False
            log_agent_response(logging.WARNING, prompt, text, status, prompt_start, prompt_end, duration, error_type, attempt_no)


    except ValidationError as e:
        prompt_end = datetime.now()
        duration = (prompt_end - prompt_start).total_seconds()
        state = False
        log_agent_response(logging.ERROR, prompt, str(e), "validation error", prompt_start, prompt_end, duration, "agent", attempt_no)

    except Exception as e:
        prompt_end = datetime.now()
        duration = (prompt_end - prompt_start).total_seconds()
        state = False
        log_agent_response(logging.ERROR, prompt, str(e),"agent error" ,prompt_start, prompt_end, duration, "agent", attempt_no)

    finally:
        db_manager.update_control_inject(int(random.random() < prob))
        return state
        
def exit_helper(db_manager: AgentDatabaseManager):
    db_manager.update_control_inject(1)
    exit(1)

def get_env_var(key, default, cast_fn):
    try:
        return cast_fn(os.getenv(key, str(default)))
    except ValueError:
        return default

def main():

    db_manager = AgentDatabaseManager("state/state.db","network.db")
    create_dbs(db_manager)
    

    toxic_prob = get_env_var("TOXIC_PROB", 0.1, float)
    tool_limit = get_env_var("TOOL_LIMIT", 1, int)
    prompt_limit = get_env_var("PROMPT_LIMIT", 1, int)

    
    api_key = os.getenv("GROQ_API_KEY",None)
    if not api_key:
        info_logger.error("API KEY not set")
        exit_helper(db_manager)

    try:
        with open("prompts.json", "r", encoding="utf-8") as f:
            prompts = json.load(f)
    except FileNotFoundError:
        info_logger.error("prompts.json file not found. Please provide a valid prompts.json file.")
        exit_helper(db_manager)
    except json.JSONDecodeError:
        info_logger.error("Invalid JSON in prompts.json file.")
        exit_helper(db_manager)

    

    llm = ChatGroq(api_key = api_key,temperature=0, model="llama3-70b-8192")
    prompt_template = hub.pull("hwchase17/structured-chat-agent")
    agent = create_structured_chat_agent(llm, TOOLS, prompt_template)
    agent_executor = AgentExecutor(agent=agent, tools=TOOLS, verbose=False)

    succ_count = 0
    count = 0

    db_manager.set_data_size(len(prompts))
    db_manager.update_control_inject(int(random.random() < toxic_prob))
    db_manager.set_network_config(tool_limit, prompt_limit, toxic_prob)
    
    overall_start = datetime.now()

    for i, item in enumerate(prompts):
        prompt = item.get("prompt")       
        if not prompt :
            info_logger.error(f"Prompt is missing in the item at index{i},Skipping this item.")
            continue
        if not isinstance(prompt,str) :
            info_logger.error(f"Prompt in the item at index {i} is not a string,Skipping this item.")
            continue    
        count += 1
        for attempt in range(prompt_limit):
            try:
                if response_handler(agent_executor, prompt, toxic_prob, db_manager):
                    succ_count += 1
                break
            except ToolLimitReachedException as e:
                if attempt == prompt_limit - 1:         
                    duration = (e.end_time - e.start_time).total_seconds() if e.start_time and e.end_time else 0
                    start_time = e.start_time if e.start_time else None
                    end_time = e.end_time if e.end_time else None
                    log_agent_response(logging.ERROR,prompt,"",600,start_time,end_time,duration,"network",prompt_limit)
                    break
                else:
                    db_manager.update_prompt_attempt(attempt + 1)
                    continue

        db_manager.update_prompt_attempt(0)
        db_manager.update_network_start(None)

        info_logger.info(json.dumps({
        "prompt_index": i,
        "event_type": "request_processed",
        "timestamp": datetime.now().isoformat(),
        "processed_count": count,
        "success_count": succ_count
        }, indent=2, ensure_ascii=False))
        
    db_manager.update_control_count(len(prompts))

    overall_stop = datetime.now()
    total_duration = (overall_stop - overall_start).total_seconds()

    info_logger.info(json.dumps({
        "start":overall_start.isoformat(),
        "end":overall_stop.isoformat(),
        "duration":total_duration,
        "# of successful requests":succ_count,
        "# of requests processed":count,
        "# of requests recieved":len(prompts),
        "configuration": {
            "toxic_probability": toxic_prob,
            "tool_limit": tool_limit,
            "prompt_limit": prompt_limit
        }
    },indent=2,ensure_ascii=False))


if __name__ == "__main__" :
    main()








