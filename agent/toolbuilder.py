import uuid
from typing import Callable,List,Union
from pydantic import BaseModel,Field
from langchain_core.tools import Tool,StructuredTool


class ToolFactory:
    def __init__(self,calling_func: Callable):
        self.calling_func = calling_func
        
    @staticmethod
    def _generate_request_id() -> str:
        return str(uuid.uuid4())

    def _search_web_method(self,query:str):
        return self.calling_func("search", "/serp", params={"q": query})

    def _get_weather_method(self,city: str):
        return self.calling_func("weather", "/weather", params={"q": city})

    def _get_event_method(self,date: str):
        return self.calling_func("calendar", "/events", params={"date": date})

    def _get_inbox_message_method(self):
        return self.calling_func("message","/inbox")
    

    def get_search_web_tool(self) -> Tool:

        return Tool(
        name="search_web",
        func= self._search_web_method,
        description="Search the internet for information. Provide a search query string as the 'query' parameter to find relevant web content."
    )


    def get_weather_tool(self) -> Tool:

        return Tool(
        name="get_weather",
        func= self._get_weather_method,
        description="Get current weather for a city. Provide the city name as the 'city' parameter (e.g., 'New York', 'London')."
    )


    def get_event_tool(self) -> Tool:

        return Tool(
        name="get_event",
        func= self._get_event_method,
        description="Get all events on a calendar date. Provide the date as the 'date' parameter in YYYY-MM-DD format."
    )


    def get_inbox_message_tool(self) -> Tool:

        return Tool(
        name = "get_inbox_message",
        func= self._get_inbox_message_method,
        description="Get messages from inbox. No input parametrer required."
    )


    def get_add_event_tool(self) -> StructuredTool:

        class EventSchema(BaseModel):
            title: str = Field(description="title of the event")
            date : str = Field(description = "date of the event in YYYY-MM-DD format",pattern=r"^\d{4}-\d{2}-\d{2}$")
            time : str = Field(description = "time of event commencement in HH:MM(24 hour)format",pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
            request_id : str = Field(default_factory= ToolFactory._generate_request_id, description="unique identifier for the request automatically generated")

        def create_event_method(input:EventSchema):
            return self.calling_func("calendar","/events",method = "POST",json_data=input.dict())

        return StructuredTool.from_function(name="add_event",func=create_event_method,description="add a calendar event.",args_schema = EventSchema)


    def get_translate_tool(self) -> StructuredTool:

        class TranslateSchema(BaseModel):
            text:str = Field(description = "text to be translated")
            source_language:str = Field(description="language of the input text")
            target_language:str = Field(description ="language to which the text is to be translated")
            request_id: str = Field(default_factory= ToolFactory._generate_request_id, description="unique identifier for the request automatically generated")

        def translate_method(input:TranslateSchema):
            return self.calling_func("translator", "/translate", method="POST", json_data=input.dict())

        return StructuredTool.from_function(name="translate",func=translate_method,description="Translate text from one language to another.",args_schema=TranslateSchema)
    

    def get_calculate_expr_tool(self) -> StructuredTool:

        class CalculateSchema(BaseModel):
            expression:str = Field(description="mathematical expression to calculate")

        def calculate_method(input:CalculateSchema):
            return self.calling_func("calculator", "/calc", method="POST", json_data=input.dict())

        return StructuredTool.from_function(name="calculate_expr",func = calculate_method,description="Perform mathematical operations.",args_schema=CalculateSchema)


    def get_send_message_tool(self) -> StructuredTool:

        class MessageSchema(BaseModel):
            to : str = Field(description="name of the person to send message to")
            body : str =Field(description="content of the message")
            request_id: str = Field(default_factory= ToolFactory._generate_request_id, description="unique identifier for the request automatically generated")

        def message_method(input:MessageSchema):
            return self.calling_func("message", "/message", method="POST", json_data=input.dict())
        
        return StructuredTool.from_function(name="send_message",description="Send a message to someone.",func=message_method,args_schema=MessageSchema)
    

    def get_search_movie_tool(self) -> StructuredTool:

        class SearchMovieSchema(BaseModel):
            query: str = Field(description="name of the movie to search for")
            language: str = Field(default="en", description="language of the movie")
            page: int = Field(default=1, ge=1, description="page number for pagination")
            per_page: int = Field(default=2, ge=1, description="number of results per page")

        def search_movie_method(input: SearchMovieSchema):
            return self.calling_func("movie", "/movie", params=input.dict())

        return StructuredTool.from_function(name="search_movie",func=search_movie_method,description="Search for a movie.",args_schema=SearchMovieSchema)
    

    def get_delete_event_by_date_tool(self) -> StructuredTool:

        class DeleteEventSchema(BaseModel):
            date :str = Field(description = "date of the event in YYYY-MM-DD format",pattern=r"^\d{4}-\d{2}-\d{2}$")
            request_id : str = Field(default_factory = ToolFactory._generate_request_id, description="unique identifier for the request automatically generated")

        def delete_event_by_date_method(input:DeleteEventSchema):
            return self.calling_func("calendar", "/events", method="DELETE",params = input.dict())

        return StructuredTool.from_function(name="delete_event_by_date", func = delete_event_by_date_method, description="Delete all events on a date,use and send unique request id.", args_schema = DeleteEventSchema)

    def get_simple_tools(self) -> List[Tool] :

        return [
            self.get_search_web_tool(),
            self.get_weather_tool(),
            self.get_event_tool(),
            self.get_inbox_message_tool()
        ]


    def get_structured_tools(self) -> List[StructuredTool]:

        return [
            self.get_add_event_tool(),
            self.get_translate_tool(),
            self.get_calculate_expr_tool(),
            self.get_send_message_tool(),
            self.get_search_movie_tool(),
            self.get_delete_event_by_date_tool()
        ]
    
    def get_all_tools(self) -> List[Union[Tool, StructuredTool]:

        return self.get_simple_tools() + self.get_structured_tools()