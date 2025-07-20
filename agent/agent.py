import os
import json
import random
import re
import uuid
import logging
import requests
import time


from langchain.agents import AgentExecutor
from langchain.agents.structured_chat.base import create_structured_chat_agent
from langchain_core.tools import Tool, StructuredTool
from langchain_groq import ChatGroq
from langchain import hub

from datetime import datetime
from pydantic import BaseModel, ValidationError, Field
from dbmanager import AgentDataBaseManager



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

services = {
        "search": "search_tool:5000",
        "weather": "weather_tool:5001", 
        "movie": "movie_tool:5002",
        "calendar": "calendar_tool:5003",
        "calculator": "calculator_tool:5004",
        "message": "message_tool:5005",
        "translator": "translator_tool:5006"
    }

inject_prev = 0
inject_next = 0
fail_count = 0


PROXY_CHECK_INTERVAL = 3
PROXY_WAIT = 30
PROXY_MGR_WAIT = 40

def get_env_var(key, default, cast_fn):
    try:
        return cast_fn(os.getenv(key, str(default)))
    except ValueError:
        return default

TOXIC_PROB = get_env_var("TOXIC_PROB", 0.1, float)
TOOL_LIMIT = get_env_var("TOOL_LIMIT", 1, int)
PROMPT_LIMIT = get_env_var("PROMPT_LIMIT", 1, int)
error_prob = get_env_var("ERROR_PROB",0.1,float)

class ToolLimitReachedException(Exception):
    def __init__(self, status_code,start_time,end_time,message):
        self.status_code = status_code
        self.start_time = start_time
        self.end_time = end_time
        self.message = message
        super().__init__(message)


def generate_request_id() -> str:
    return str(uuid.uuid4())


def get_proxy_status(tool_name):
    try:
        response = requests.get(f"http://toxiproxy:{PROXY[tool_name]}/", timeout=5)
        return response.status_code == 200
    except (requests.exceptions.Timeout,requests.exceptions.ConnectionError) as e:
        info_logger.error(f"Tool {tool_name} not responding in time")
        return False
    except Exception as e:
        info_logger.error(f"Error checking status of {tool_name}: {str(e)}")
        return False
   

def proxy_mgr_status(param = None):
    try:
        response = requests.get(f"http://proxy_mgr:8000/health",timeout = 5)
        return response.status_code==200
   
    except Exception as e:
        info_logger.error(f"Error checking status of proxy mgr: {str(e)}")
        return False


def active(status,wait,interval,tool_name = None):
    if status(tool_name): 
        return True
        
    wait_time = 0
    info_logger.error(f"{tool_name} Proxy is down,waiting for maximum of {wait}s to restart")
    
    while wait_time < wait:
        if wait_time + interval <= wait:
            sleep_interval = interval
            wait_time += interval
        else:
            sleep_interval = wait - wait_time
            wait_time = wait
        
        time.sleep(sleep_interval)
        
        if status(tool_name):  
            info_logger.info(f"{tool_name} Proxy is up after {wait_time}s,continuing with proxy")
            return True
    
    info_logger.info(f"{tool_name} Proxy remains unreachable")
    return False



def update_inject_with_smart_wait(db_manager: AgentDataBaseManager, prob: float):
    
    global inject_prev, inject_next, fail_count
    
    if not active(proxy_mgr_status,PROXY_MGR_WAIT,PROXY_CHECK_INTERVAL):
        return

    row = db_manager.get_inject_state()
    if row:
        inject_prev,inject_next,fail_count = row
    else:
        inject_prev,inject_next,fail_count = 0,0,0
   

    if fail_count == 0:
        inject_next = int(random.random() < prob)
        db_manager.update_network_inject(inject_next)
        
    if inject_next == inject_prev:
        time.sleep(0.05)
    else:
        wait_times = [0.2,0.4,0.6,0.8,1.0]
        for wait in wait_times :
            time.sleep(wait)
            try:
                no_pending_events = db_manager.fetch_event_status()
                if no_pending_events:
                    time.sleep(0.05)
                    break
            except:
                pass

    inject_prev = inject_next
    fail_count = 0

    for i in range(3):
        try:
            db_manager.update_inject_state(inject_prev,inject_next,fail_count)
            break
        except Exception as e:
            info_logger.error(f"attempt {i+1}:Database error in updating injection state: {str(e)},retry with new transaction")
            time.sleep(0.02)
            
    

def call_service_directly(tool_name, endpoint, method, params=None, json_data=None,attempts = 0):
    
    if tool_name not in services:
        return {"result": f"No direct fallback available for {tool_name}", "status": 504}
    
    direct_url = f"http://{services[tool_name]}{endpoint}"
    
    try:
       
        if method == "GET":
            res = requests.get(direct_url, params=params or {}, timeout=5)
        elif method == "POST":
            res = requests.post(direct_url, json=json_data or {}, timeout=5)
        elif method == "DELETE":
            res = requests.delete(direct_url, params=params or {}, timeout=5)
            
        info_logger.info(json.dumps({
            "fallback_used": True,
            "direct_url": direct_url,
            "message":f"tool {tool_name} fall_back after {attempts} tool level-network tries"
        }, indent=2, ensure_ascii=False))
        
        return {
            "result":res.json(),
            "status":503
        }
        
    except Exception as e:
        info_logger.error(json.dumps({
            "fallback_used": True,
            "direct_url": direct_url,
            "message":f"Direct fallback failed after {attempts} tool level-network tries for {tool_name}:{str(e)}"
            },indent=2, ensure_ascii=False))

        return {"result":f"Both proxy and direct access failed for {tool_name}","status": 500}



def call_with_toxic(tool_name, endpoint, method="GET", params=None, json_data=None):
    
    if not active(get_proxy_status,PROXY_WAIT,PROXY_CHECK_INTERVAL,tool_name):
        raise Exception(f"tool {tool_name} failure")

    if random.random() < error_prob:
        raise Exception(f"simulating tool {tool_name} failure")

    proxy = PROXY[tool_name]
    url = f"http://toxiproxy:{proxy}{endpoint}"
    tool_attempts = 0
    tool_limit = TOOL_LIMIT
    prompt_limit = PROMPT_LIMIT
    prob = TOXIC_PROB

    db_manager = AgentDataBaseManager("state/state.db","network.db")
    row = db_manager.get_network_state()
    
    if row:
        prompt_attempt,start = row
        if not start:
            start = datetime.now().isoformat()
            db_manager.update_network_start(start)
    else:
        prompt_attempt,start = 0,datetime.now().isoformat()

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
            
            if tool_attempts >= tool_limit :
                return {"result": "Tool limit exceeded", "status": 600}

            if isinstance(e, requests.exceptions.Timeout):
                info_logger.error(f"{tool_name} timed out at endpoint {endpoint} after {tool_attempts} tool attempts in {prompt_attempt} prompt attempts")
            elif isinstance(e,requests.exceptions.ConnectionError):
                info_logger.error(f"Connection aborted with {tool_name} at endpoint {endpoint} after {tool_attempts} tool attempts in {prompt_attempt} prompt attempts")

            update_inject_with_smart_wait(db_manager,prob)
            continue
                
        except Exception as e:
            info_logger.error(f"{str(e)},Using direct fallback")
            return call_service_directly(tool_name, endpoint, method, params, json_data,tool_attempts)

        
        
class EventSchema(BaseModel):
    title: str = Field(description="title of the event")
    date : str = Field(description = "date of the event in YYYY-MM-DD format",pattern=r"^\d{4}-\d{2}-\d{2}$")
    time : str = Field(description = "time of event commencement in HH:MM(24 hour)format",pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    request_id : str = Field(default_factory= generate_request_id, description="unique identifier for the request automatically generated")
def event_method(input:EventSchema):
    return call_with_toxic("calendar", "/events",method = "POST",json_data=input.dict())
add_event = StructuredTool.from_function(name="add_event",func=event_method,description="add a calendar event.",args_schema = EventSchema)






class TranslateSchema(BaseModel):
    text:str = Field(description = "text to be translated")
    source_language:str = Field(description="language of the input text")
    target_language:str = Field(description ="language to which the text is to be translated")
    request_id: str = Field(default_factory= generate_request_id, description="unique identifier for the request automatically generated")
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
    request_id: str = Field(default_factory=generate_request_id, description="unique identifier for the request automatically generated")
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




def search_web_method(query:str):
    return call_with_toxic("search", "/serp", params={"q": query})

def get_weather_method(city: str):
    return call_with_toxic("weather", "/weather", params={"q": city})

def delete_event_by_date_method(date: str):
    return call_with_toxic("calendar", "/events", method="DELETE", params={"date": date, "request_id": generate_request_id})

def get_event_method(date: str):
    return call_with_toxic("calendar", "/events", params={"date": date})

def get_inbox_message_method():
    return call_with_toxic("message","/inbox")



TOOLS = [
    Tool(
        name="search_web",
        func= search_web_method,
        description="Search the internet for information. Provide a search query string as the 'query' parameter to find relevant web content."
    ),
    Tool(
        name="get_weather",
        func= get_weather_method,
        description="Get current weather for a city. Provide the city name as the 'city' parameter (e.g., 'New York', 'London')."
    ),
    search_movie,
    add_event,
    Tool(
        name="delete_event_by_date",
        func= delete_event_by_date_method,
        description="Delete all events on a date,use and send unique request id. Provide the date as the 'date' parameter in YYYY-MM-DD format. A unique request ID is automatically generated."
    ),
    Tool(
        name="get_event",
        func= get_event_method,
        description="Get all events on a calendar date. Provide the date as the 'date' parameter in YYYY-MM-DD format."
    ),
    translate,
    calculate_expr,
    send_message,
    Tool(
        name = "get_inbox_message",
        func= send_message_method,
        description="Get messages from inbox. No input parametrer required."
    )
]


def create_dbs(db_manager:AgentDataBaseManager):
    os.makedirs("state", exist_ok=True)
    os.makedirs("network",exist_ok = True)
    db_manager.init_dbs()

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


def response_handler(agent_executor: AgentExecutor, prompt: str, prob:float,db_manager:AgentDataBaseManager):
    state = True
    row = db_manager.get_network_state()
    if row:
        attempt_no = row[0] + 1
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
       update_inject_with_smart_wait(db_manager,prob)
       return state
        
def exit_helper(db_manager: AgentDataBaseManager):
    db_manager.signal_exit()
    exit(1)

def main():

    db_manager = AgentDataBaseManager("state/state.db","network.db")
    create_dbs(db_manager)
    
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
    update_inject_with_smart_wait(db_manager,int(random.random() < TOXIC_PROB))
    db_manager.set_network_config(TOOL_LIMIT, PROMPT_LIMIT, TOXIC_PROB)
    
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
        for attempt in range(PROMPT_LIMIT):
            try:
                if response_handler(agent_executor, prompt, TOXIC_PROB, db_manager):
                    succ_count += 1
                break
            except ToolLimitReachedException as e:
                if attempt == PROMPT_LIMIT - 1:         
                    duration = (e.end_time - e.start_time).total_seconds() if e.start_time and e.end_time else 0
                    start_time = e.start_time if e.start_time else None
                    end_time = e.end_time if e.end_time else None
                    log_agent_response(logging.ERROR,prompt,"",600,start_time,end_time,duration,"network",PROMPT_LIMIT)
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

        time.sleep(0.01)

    db_manager.signal_exit()

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
            "toxic_probability": TOXIC_PROB,
            "tool_limit": TOOL_LIMIT,
            "prompt_limit": PROMPT_LIMIT
        }
    },indent=2,ensure_ascii=False))


if __name__ == "__main__" :
    main()








