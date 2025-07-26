class Default :
    def __init__(self):

        self.proxy = {
            "search": "6000",
            "weather": "6001", 
            "movie": "6002",
            "calendar": "6003",
            "translator": "6006",
            "calculator": "6004",
            "message": "6005"
        }

        self.services = {
            "search": "search_tool:5000",
            "weather": "weather_tool:5001",
            "movie": "movie_tool:5002", 
            "calendar": "calendar_tool:5003",
            "calculator": "calculator_tool:5004",
            "message": "message_tool:5005",
            "translator": "translator_tool:5006",
            "proxy_mgr": "proxy_mgr:8000"
        }

        self.intervals = {
            "proxy_check_interval": 3,
            "proxy_wait": 30,
            "proxy_mgr_wait": 40,
            "proxy_timeout": 5,
            "fallback_timeout": 10
        }

        self.files = {"prompts":"prompts.json"}

    def get_services(self):
        return self.services

    def get_proxies(self):
        return self.proxy

    def get_intervals(self):
        return self.intervals
    
    def get_files(self):
        return self.files

    def get_all(self):
        return (self.get_proxies(), self.get_services(), self.get_intervals(), self.get_files())

