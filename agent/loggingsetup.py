import logging
import json

def create_loggers(dir):
   
    info_logger = logging.getLogger("info")
    info_handler = logging.FileHandler(f"{dir}/info.log")
    info_logger.setLevel(logging.INFO)
    info_handler.setFormatter(logging.Formatter("%(asctime)s [agent] %(message)s"))
    if not info_logger.handlers:
        info_logger.addHandler(info_handler)

    agent_logger = logging.getLogger("agent")
    agent_handler = logging.FileHandler(f"{dir}/agent.log")
    agent_logger.setLevel(logging.INFO)
    if not agent_logger.handlers:
        agent_logger.addHandler(agent_handler)

    return info_logger, agent_logger


def log_direct_service_call(logger, tool_name, endpoint, direct_url, attempts, prompt_attempt, event_type, error=None):

    base_log_data = {
        "tool": tool_name,
        "endpoint": endpoint,
        "direct_url": direct_url,
        "tool_attempts": attempts + 1,
        "prompt_attempts": prompt_attempt,
        "fallback_used": True
    }

    if event_type == "success":
        log_data = {
            **base_log_data,
            "status": "success",
            "message": f"Direct fallback succeeded for {tool_name} after {attempts + 1} tool level tries in {prompt_attempt} prompt level attempts"
        }
        logger.info(json.dumps(log_data, indent=2, ensure_ascii=False))

    elif event_type == "timeout":
        log_data = {
            **base_log_data,
            "status": "timeout",
            "message": f"{tool_name} timed out at endpoint {endpoint} after {attempts + 1} tool level tries in {prompt_attempt} prompt level attempts"
        }
        logger.error(json.dumps(log_data, indent=2, ensure_ascii=False))

    elif event_type == "connection_error":
        log_data = {
            **base_log_data,
            "status": "connection_error",
            "message": f"Connection aborted with {tool_name} at endpoint {endpoint} after {attempts + 1} tool level tries in {prompt_attempt} prompt level attempts"
        }
        logger.error(json.dumps(log_data, indent=2, ensure_ascii=False))

    elif event_type == "fallback_failed":
        log_data = {
            **base_log_data,
            "status": "fallback_failed",
            "error": str(error) if error else "Unknown Error",
            "message": f"Direct fallback failed after {attempts + 1} tool level-network tries for {tool_name} in {prompt_attempt} prompt level attempts"
        }
        logger.error(json.dumps(log_data, indent=2, ensure_ascii=False))

def log_agent_response(logger, log_level, prompt, response, status, start_time, end_time, duration, error_type, attempt_no):

    log_data = {
        "prompt": prompt,
        "response": response,
        "status": status,
        "start_time": start_time ,
        "end_time": end_time ,
        "duration": duration,
        "error_type": error_type,
        "prompt_attempt_no": attempt_no
    }

    log_message = json.dumps(log_data, indent=2, ensure_ascii=False)

    if log_level == "info":
        logger.info(log_message)
    elif log_level == "warning":
        logger.warning(log_message)
    elif log_level == "error":
        logger.error(log_message)
