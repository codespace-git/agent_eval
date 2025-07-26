import os
import json
import sys
import random
import re
import requests
import time
from datetime import datetime
from pydantic import ValidationError

from langchain.agents import AgentExecutor
from langchain.agents.structured_chat.base import create_structured_chat_agent
from langchain_groq import ChatGroq
from langchain import hub

from defaults import Default
from toolbuilder import ToolFactory
from dbmanager import AgentDataBaseManager
from contentsloader import AgentConfigLoader
from utilities import Utils, ToolLimitReachedException, FileLoadingException
from loggingsetup import create_loggers, log_direct_service_call, log_agent_response




os.makedirs("logs", exist_ok=True)
info_logger,agent_logger = create_loggers("logs")

loader = AgentConfigLoader("config.json")

default = Default()
PROXY,services,intervals,file_paths = default.get_all()

def config_init(config:dict):
    try:
        proxy = config["proxy"]
        services = config["services"]
        intervals = config["intervals"] 
        file_paths = config["files"]
        return proxy,services,intervals,file_paths
    except KeyError as e:
        info_logger.error(f"item not found:{str(e)},using default values")
        return default.get_all()

try:
    package = loader.load_config("config.json")
    if not package:
        info_logger.warning("config file is empty,using default values")
    else:
        items = ["proxy","services","intervals","files"]
        try:
            config = loader.unpackage(package,items)
            PROXY,services,intervals,file_paths = config_init(config)
        except FileLoadingException as e:
            info_logger.error(e.message)
except JSON.DecodeError as e:
    info_logger.error("config file could not be loaded,using default values")
except FileNotFoundError as e:
    info_logger.error("no config file found,using default values")


inject_prev = 0
inject_next = 0
fail_count = 0

special_strings = ["Tool limit reached"]


PROXY_CHECK_INTERVAL = intervals["proxy_check_interval"]
PROXY_WAIT = intervals["proxy_wait"]
PROXY_MGR_WAIT = intervals["proxy_mgr_wait"]
PROXY_TIMEOUT = intervals["proxy_timeout"]
FALLBACK_TIMEOUT = intervals["fallback_timeout"]


def get_env_var(key, default, cast_fn):
    try:
        return cast_fn(os.getenv(key, str(default)))
    except ValueError:
        return default

TOXIC_PROB = get_env_var("TOXIC_PROB", 0.1, float)
TOOL_LIMIT = get_env_var("TOOL_LIMIT", 1, int)
PROMPT_LIMIT = get_env_var("PROMPT_LIMIT", 1, int)
ERROR_PROB = get_env_var("ERROR_PROB",0.1,float)



util = Utils(PROXY,services,PROXY_TIMEOUT,info_logger)


def update_inject_with_smart_wait(db_manager: AgentDataBaseManager, prob: float):
    
    global inject_prev, inject_next, fail_count
    
    if not util.active(PROXY_MGR_WAIT,PROXY_CHECK_INTERVAL):
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
            


def call_service_directly(tool_name, endpoint, method, params=None, json_data=None,attempts = 0,prompt_attempt = 0):
    
    if tool_name not in services:
        return {"result": f"No direct fallback available for {tool_name}", "status": 504}
    
    direct_url = f"http://{services[tool_name]}{endpoint}"
    while attempts < TOOL_LIMIT:

        try:
       
            if method == "GET":
                res = requests.get(direct_url, params=params or {}, timeout=FALLBACK_TIMEOUT)
            elif method == "POST":
                res = requests.post(direct_url, json=json_data or {}, timeout=FALLBACK_TIMEOUT)
            elif method == "DELETE":
                res = requests.delete(direct_url, params=params or {}, timeout=FALLBACK_TIMEOUT)
            
            log_direct_service_call(info_logger,tool_name, endpoint, direct_url, attempts, prompt_attempt, "success")
        
            return {
                "result":res.json(),
                "status":200
            }
        except (requests.exceptions.Timeout,requests.exceptions.ConnectionError) as e:
            attempts += 1
            
            if attempts >= TOOL_LIMIT:
               return {"result": "Tool limit reached", "status": 600}

            if isinstance(e, requests.exceptions.Timeout):
                log_direct_service_call(info_logger,tool_name, endpoint, direct_url, attempts-1, prompt_attempt, "timeout")
            elif isinstance(e,requests.exceptions.ConnectionError):
               log_direct_service_call(info_logger,tool_name, endpoint, direct_url, attempts-1, prompt_attempt, "connection_error")
            continue

        except Exception as e:
            log_direct_service_call(info_logger,tool_name, endpoint, direct_url, attempts, prompt_attempt,"fallback_failed",e)
            return {"result":f"Both proxy and direct access failed for {tool_name}","status": 600}



def call_with_toxic(tool_name, endpoint, method="GET", params=None, json_data=None):
    
    tool_attempts = None
    prompt_attempt = None

    if not util.active(PROXY_WAIT,PROXY_CHECK_INTERVAL,tool_name):
        raise Exception(f"tool {tool_name} failure")

    if random.random() < ERROR_PROB:
        raise Exception(f"simulating tool {tool_name} failure")

    proxy = PROXY[tool_name]
    url = f"http://toxiproxy:{proxy}{endpoint}"
    
    db_manager = AgentDataBaseManager("state/state.db","network.db")
    row = db_manager.get_network_state()
    
    if row:
        prompt_attempt,start = row
        if not start:
            start = datetime.now().isoformat()
            db_manager.update_network_start(start)
    else:
        prompt_attempt = 0
        start = datetime.now().isoformat()
    
    tool_attempts = 0

    while tool_attempts < TOOL_LIMIT :
        try:
            
            if method == "GET":
                res = requests.get(url, params=params or {}, timeout=PROXY_TIMEOUT)
            elif method == "POST":
                res = requests.post(url, json=json_data or {}, timeout=PROXY_TIMEOUT)
            elif method == "DELETE":
                res = requests.delete(url, params=params or {}, timeout=PROXY_TIMEOUT)


            network_end = datetime.now()
            network_start = datetime.fromisoformat(start)
            network_latency = (network_end - network_start).total_seconds()
            total_attempts = (TOOL_LIMIT*prompt_attempt)+tool_attempts + 1
            

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
            
            if tool_attempts >= TOOL_LIMIT :
                return {"result": "Tool limit reached", "status": 600}

            if isinstance(e, requests.exceptions.Timeout):
                info_logger.error(f"{tool_name} timed out at endpoint {endpoint} after {tool_attempts} tool attempts in {prompt_attempt} prompt attempts")
            elif isinstance(e,requests.exceptions.ConnectionError):
                info_logger.error(f"Connection aborted with {tool_name} at endpoint {endpoint} after {tool_attempts} tool attempts in {prompt_attempt} prompt attempts")

            update_inject_with_smart_wait(db_manager,TOXIC_PROB)
            continue
                
        except Exception as e:
            info_logger.error(f"{str(e)},Using direct fallback")
            return call_service_directly(tool_name, endpoint, method, params, json_data,tool_attempts if tool_attempts else 0,prompt_attempt if prompt_attempt else 0)


toolfactory = ToolFactory(call_with_toxic)
TOOLS = toolfactory.get_all_tools()


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
                res = parsed_data.get("result")
                if status == 600:
                    raise ToolLimitReachedException(600,prompt_start,prompt_end,str(res))
                if 400<=status<600:
                    state=False
                log_agent_response(agent_logger,"info", prompt, res , status, prompt_start.isoformat() if prompt_start else "", prompt_end.isoformat() if prompt_end else "", duration, util.error_classifier(status), attempt_no)

            except json.JSONDecodeError:
                error_type,status = util.error_classifier(data)
                if status == 600:
                    raise ToolLimitReachedException(600,prompt_start,prompt_end,special_strings[0])
                if 400<=status<600:
                    state = False
                log_agent_response(agent_logger,"warning",prompt, data, status,prompt_start.isoformat() if prompt_start else "", prompt_end.isoformat() if prompt_end else "", duration, error_type, attempt_no)
        

        elif isinstance(data,dict):
            status = data.get("status")
            res = data.get("result")
            if status == 600:
                raise ToolLimitReachedException(600,prompt_start,prompt_end,str(res))
            if 400<=status<600 :
                state=False
            log_agent_response(agent_logger,"info", prompt, data.get("result"), status,prompt_start.isoformat() if prompt_start else "", prompt_end.isoformat() if prompt_end else "", duration, util.error_classifier(status), attempt_no)
        
        else:
            text = str(data)
            error_type,status = util.error_classifier(text)
            if status == 600:
                raise ToolLimitReachedException(600,prompt_start,prompt_end,special_strings[0])
            if 400<=status<600:
                state = False
            log_agent_response(agent_logger,"warning",prompt, text, status, prompt_start.isoformat() if prompt_start else "", prompt_end.isoformat() if prompt_end else "", duration, error_type, attempt_no)


    except ValidationError as e:
        prompt_end = datetime.now()
        duration = (prompt_end - prompt_start).total_seconds()
        state = False
        log_agent_response(agent_logger,"error",prompt, str(e), "validation error", prompt_start.isoformat() if prompt_start else "", prompt_end.isoformat() if prompt_end else "", duration, "agent", attempt_no)

    except Exception as e:
        prompt_end = datetime.now()
        duration = (prompt_end - prompt_start).total_seconds()
        state = False
        log_agent_response(agent_logger,"error", prompt, str(e),"agent error" ,prompt_start.isoformat() if prompt_start else "", prompt_end.isoformat() if prompt_end else "", duration, "agent", attempt_no)

    finally:
       update_inject_with_smart_wait(db_manager,prob)
       return state
        
def exit_helper(db_manager: AgentDataBaseManager):
    db_manager.signal_exit()
    sys.exit(1)

def main():

    db_manager = AgentDataBaseManager("state/state.db","network.db")

    os.makedirs("state", exist_ok=True)
    os.makedirs("network",exist_ok = True)
    db_manager.init_dbs()
   
    
    api_key = os.getenv("GROQ_API_KEY",None)
    if not api_key:
        info_logger.error("API KEY not set")
        exit_helper(db_manager)

    prompts = []

    try:
        path = file_path["prompts"]
        with open(path, "r", encoding="utf-8") as f:
            prompts = json.load(f)
        if not prompts:
            info_logger.warning("prompts.json is empty,exiting")
            exit_helper(db_manager)
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
    update_inject_with_smart_wait(db_manager, TOXIC_PROB)

    
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
                    if e.message == special_strings[0] :
                        log_agent_response(agent_logger,"error",prompt,e.message,600,e.start_time.isoformat() if e.start_time else "",e.end_time.isoformat() if e.end_time else "",duration,"network",PROMPT_LIMIT)
                    else:
                        log_agent_response(agent_logger,"error",prompt,e.message,600,e.start_time.isoformat() if e.start_time else "",e.end_time.isoformat() if e.end_time else "",duration,"server",PROMPT_LIMIT)
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
        "# of requests received":len(prompts),
        "configuration": {
            "toxic_probability": TOXIC_PROB,
            "failure_probability":ERROR_PROB,
            "tool_limit": TOOL_LIMIT,
            "prompt_limit": PROMPT_LIMIT
        }
    },indent=2,ensure_ascii=False))


if __name__ == "__main__" :
    main()








