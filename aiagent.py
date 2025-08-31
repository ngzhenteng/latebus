# from langchain_tavily import TavilySearch
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages.ai import AIMessage
from langchain_core.messages.tool import ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import trim_messages
from langchain_core.messages import RemoveMessage
from langchain_core.messages.system import SystemMessage

import os
from busutils import BusUtils
from model.ai_bus_arr_card import AiBusArrCard
from sort_strategy.service_no_sort_strategy import ServiceNoSortStrategy

class AiAgent:
    search = None
    model = None
    agent_executor = None
    llm_memory = None

    message_context_window = 10
    check_prompter_message_window = 15

    def __init__(self, bus_utils: BusUtils):
        if bus_utils is None: raise Exception("bus_utils None in constructor")
        # self.search = TavilySearch(max_results=2)
        self.model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
        self.bus_utils = bus_utils
        self.init_agent_executor()

    def init_agent_executor(self):
        if self.agent_executor is not None: return
        # TODO: create tool that lists bus stops.
        
        @tool
        def search_busstop(description: str):
            """Get all bus stops with a description similar to 'description'"""
            return self.bus_utils.search_busstop(description=description)

        @tool
        def get_bus_timings_via_bus_stop_code(bus_stop_code: str) -> str:
            """Get bus arrival timings at a bus stop via the bus_stop_code. bus_stop_code is found in the search_busstop response.
            Pass BusStopCode as bus_stop_code argument in this tool, pass Description as bus_stop_desc argument in this tool. Always return the returned value of this tool as-is."""
            result = "Reproduce this hyperlink and table exactly as it is, do not rephrase anything after +----------------------------------------+\n" + self.bus_utils.get_bus_timings(bus_stop_code=bus_stop_code, sortStrategy=ServiceNoSortStrategy())
            return result
        
        def delete_messages(state):
            messages_to_remove = state["messages"]
            # messages_to_remove = [m for m in messages if not isinstance(m, SystemMessage)] system message is passed in each query, no need to skip it.
            if len(messages_to_remove) > self.check_prompter_message_window:
                return {"messages": [RemoveMessage(id=m.id) for m in messages_to_remove[:-self.check_prompter_message_window]]}

        # This function will be called every time before the node that calls LLM
        def pre_model_hook(state):
            trimmed_messages = trim_messages(state["messages"], strategy="last", max_tokens=self.message_context_window, token_counter=len, start_on="human", end_on=("human", "tool"))
            # You can return updated messages either under `llm_input_messages` or 
            # `messages` key (see the note below)
            return {"llm_input_messages": trimmed_messages}

        tools = [search_busstop, get_bus_timings_via_bus_stop_code]
        self.llm_memory = MemorySaver()
        self.agent_executor = create_react_agent(self.model, tools, checkpointer=self.llm_memory, pre_model_hook=pre_model_hook, post_model_hook=delete_messages)

    def handle_user_msg(self, input: str, chat_id: str) -> AiBusArrCard:
        
        system_message = {
            "role": "system", "content": "Your only purpose is to help users find bus stops and bus arrival times."
            "Always first try to search for the bus stop code using 'search_busstop' tool, if the prompt does not provide."
            "Never list the bus stop code without its description."
            "When you come across a table from the 'get_bus_timings_via_bus_stop_code' tool such as "
            "+----------------------------------------+"
            "| Arriving at Hotel Grand Pacific |"
            "+-------+---------------+----------------+"
            "|  Bus  |     Coming    |      Next      |"
            "+-------+---------------+----------------+"
            "|   12  |     16m 1s    |     28m 1s     |"
            "|  12e  |     35m 7s    |       NA       |"
            "|  175  |     4m 44s    |    28m 19s     |"
            "+-------+---------------+----------------+"
            "include the table as-is in your response"}
        input_message = {"role": "user", "content": input}
        config = {"configurable": {"thread_id": chat_id}}
        response = self.agent_executor.invoke({"messages": [system_message, input_message]}, config=config)

        bus_stop_code = None
        final_ai_msg = None

        response_msgs = response["messages"]
        # logic to send update button, only when 2 messages before the AI Message has a tool call to get_bus_timings_via_bus_stop_code
        scnd_last_msg = response_msgs[-3] if len(response_msgs) > 2 else None
        if scnd_last_msg and isinstance(scnd_last_msg, AIMessage) and scnd_last_msg.tool_calls:
            for tool_call in scnd_last_msg.tool_calls:
                if tool_call["name"] == "get_bus_timings_via_bus_stop_code": 
                    bus_stop_code = tool_call["args"]["bus_stop_code"]
        if not final_ai_msg: final_ai_msg = response_msgs[-1].content
        return AiBusArrCard(final_ai_msg, bus_stop_code)