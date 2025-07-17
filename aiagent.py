from langchain_tavily import TavilySearch
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.tool import ToolMessage

import os
from busutils import BusUtils
from model.ai_bus_arr_card import AiBusArrCard

class AiAgent:
    search = None
    model = None

    def __init__(self):
        self.search = TavilySearch(max_results=2)
        self.model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")


    def handle_user_msg(self, input: str, bus_utils: BusUtils) -> AiBusArrCard:
        # search_results = search.invoke("What is the weather in Singapore")
        # print(search_results)
        
        @tool
        def search_busstop(description: str):
            """Get all bus stops with a description similar to 'description'"""
            return bus_utils.search_busstop(description=description)

        # @tool
        # def get_bus_timings_via_bus_stop_desc(bus_stop_desc: str):
        #     """Get bus arrival timings at a bus stop, via the bus stop name, 
        #     which is found in the Description json response field in the all_busstops_tool tool's response.
        #     pass Description as bus_stop_desc argument in this tool"""
        #     return bus_utils.get_bus_timings_via_bus_stop_desc(bus_stop_desc)

        @tool
        def get_bus_timings_via_bus_stop_code(bus_stop_code: str, bus_stop_desc: str = None) -> str:
            """Get bus arrival timings at a bus stop via the bus_stop_code. bus_stop_code is found in the search_busstop response.
            Pass BusStopCode as bus_stop_code argument in this tool, pass Description as bus_stop_desc argument in this tool"""
            return bus_utils.get_bus_timings(bus_stop_code=bus_stop_code, bus_stop_desc=bus_stop_desc)

        tools = [self.search, search_busstop, get_bus_timings_via_bus_stop_code]

        # model_with_tools = model.bind_tools(tools)

        # query = "Search for the weather in Singapore"
        # response = model_with_tools.invoke([{"role": "user", "content": query}])

        # print(f"Message content: {response.text()}\n")
        # print(f"Tool calls: {response.tool_calls}")

        agent_executor = create_react_agent(self.model, tools)

        # prompt_template = ChatPromptTemplate.from_messages(
        #     [("system", "Always preserve the responses from get_bus_timings_via_bus_stop_code tool"), ("user", "{text}")]
        # )
        # prompt_template.invoke({"text": "What time are busses arriving at bugis station exit b? Always search for the bus stop code if not provided"})
        system_message = {"role": "system", "content": "You are an agent that helps users find bus stops and bus arrival times. Always search for the bus stop code using search_busstop tool if the prompt does not provide. Other than the get_bus_timings_via_bus_stop_code tool, you may format your answers in lists where suitable"}
        input_message = {"role": "user", "content": input}
        response = agent_executor.invoke({"messages": [system_message, input_message]})

        bus_stop_code = None
        final_ai_msg = None
        for message in response["messages"]:
            message.pretty_print()
            if isinstance(message, ToolMessage):
                if message.name == "get_bus_timings_via_bus_stop_code":
                    final_ai_msg = message.content
            if not isinstance(message, AIMessage) or not message.tool_calls or bus_stop_code:
                continue
            for tool_call in message.tool_calls:
                if tool_call["name"] == "get_bus_timings_via_bus_stop_code": 
                    bus_stop_code = tool_call["args"]["bus_stop_code"]

        response_msgs = response["messages"]
        if not final_ai_msg: final_ai_msg = response_msgs[-1].content
        return AiBusArrCard(final_ai_msg, bus_stop_code)