import json
from typing import Callable,List
from utilities import LoadingException

class AgentConfigLoader:
    def __init__(self, path):
        self.path = path

    def load_config(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except FileNotFoundError as e:
           raise 
        except json.JSONDecodeError as e:
           raise 

        return config

    def order_items(self,package:dict,items: List[str]) -> List[str]:
        key_items = []
        for key in package.keys():
            if key in items:
                key_items.append(key)
        return key_items
    
    def unpackage(self,package:dict, items: List[str],ordering:Callable[[List[str]],List[str]] = None) -> dict:
        if ordering is None:
            ordering = self.order_items
        if not items:
            raise FileLoadingException("invalid requirement list,using default values")

        ordered_items = ordering(package,items)
        unpackaged = {}

        for item in ordered_items:
            value = package.get(item)
            if not value:
                raise FileLoadingException(f"{item} not found,using default values")
            unpackaged[item] = value

        return unpackaged

