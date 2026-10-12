# graph.py
from langgraph.graph import StateGraph, START, END
from state import SupportState
from nodes import (
    guardrail_node,
    #hyde_rewriter_node,
    route_query,
    refusal_node,
    
    
)
from rag2 import rag_execution_node,hyde_rewriter_node
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

# Thread memory: current conversation
g_checkpointer=InMemorySaver()

# Long-term memory, cross session preferences
g_store=InMemoryStore()

from langgraph.store.base import BaseStore
from langchain_core.runnables import RunnableConfig
from rag import policy_chain, search_hotel_policies
from api_tools import list_available_rooms
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from nodes import llm
from subgraphs.cancel_graph import cancel_subgraph




# 1. Define the Execution Nodes (The Actions)
def api_node(state: SupportState):
    print("---NODE: API EXECUTION---")
    # General availability questions do not require booking dates.
    api_result = list_available_rooms.invoke({})
    # Pass the result to the LLM to format a nice response
    final_response = llm.invoke(f"User asked: {state['user_query']}. API data: {api_result}. Give a helpful response.")
    return {"messages": [final_response]}

def rag_node(state: SupportState):
    print("---NODE: RAG EXECUTION---")
    # Use the transformed query (HyDE) for better vector search
    context = search_hotel_policies.invoke(state["transformed_query"])
    #update our retrieved_context field for rag evaluation
    #state['retrieved_contexts']=context
    # Pass to our strict policy chain
    final_response = policy_chain.invoke({"context": context, "question": state["user_query"]})
    return {"messages": [AIMessage(content=final_response)]}
from subgraphs.book_graph import booking_app
def create_booking_node(state:SupportState, config:RunnableConfig):
    result=booking_app.invoke({
        "user_query":state["user_query"]
    },
    config=config)
    response=result.get("response")
    if response:
        return {
            "messages":[
                AIMessage(content=str(response))
            ]
        }
    return result
def cancellation_node(state: SupportState, config: RunnableConfig):
    """Delegate cancellation verification and admin approval to the cancellation subgraph."""
    result = cancel_subgraph.invoke({
        "role": "guest",
        "user_query": state["user_query"],
    }, config=config)

    if result.get("response"):
        return {"messages": [AIMessage(content=str(result["response"]))]}
    return result


from pydantic import BaseModel, Field
class RoomNumberExtraction(BaseModel):
    room_number: int | None = Field(
        default=None,
        description="The hotel room number explicitly mentioned by the user.",
    )


def extract_room_number_node(state: SupportState):
    """Extract a room number only when the current request provides one."""
    room_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Extract a hotel room number only if the user explicitly provides one. "
            "Return null when no room number is present. Do not guess.",
        ),
        ("human", "{user_query}"),
    ])
    extractor = room_prompt | llm.with_structured_output(RoomNumberExtraction)
    result = extractor.invoke({"user_query": state["messages"]})

    if result.room_number is not None:
        print(f"---Remembering room {result.room_number} for this conversation---")
        return {"room_number": result.room_number}

    print(f"---Using remembered room {state.get('room_number')}---")
    return {}
    
def validate_room_number_node(state:SupportState):
    print("----- Validation of room number----")
    if not state.get("room_number"):
        print("validation failed no room assigned.")
        # Route to a node that politely explains they need to check in.
        return "unauthorized-access"
    print("validation passed, room number retrieved.")
    return "execute_room_service"

from pydantic import BaseModel, Field
from typing import List

class RoomServiceOrder(BaseModel):
    """Extracts the food and amenities the guest wants to order."""
    items:List[str]=Field(
        description="The list of items to order.ONLY extract items if they match this menu:Burger, Fries, Club Sandwich, Soda, Towels, Extra Pillows."
    )
def extract_order_node(state:SupportState):
    print("---Extracting order items----")
    # 1. Bind the pydantic schema to LLM
    structured_llm=llm.with_structured_output(RoomServiceOrder)
    
    #2. Pass the user's query into the structured LLM
    # e.g. user_query: "I'm starving, send two burgers and a soda"
    result=structured_llm.invoke(state['messages'])
    # 3. Update the state with the extracted list: ["Burger", "Burger", "Soda"]
    print(f"Extracted Items: {result.items}")
    return {"extracted_items": result.items}

def execute_room_service_node(state:SupportState):
    items=state.get("extracted_items",[])
    room_number=state.get("room_number")
    
    print(f"Executing API: Charging {items} to Room {room_number}")
    return {"messages": [f"Ordered {', '.join(items)} for Room {room_number}."]}
"""Context Bloat: If you store every single "Hello" and "Thank you" a user has ever said over the last year, injecting that into the LLM's prompt will exceed the token limit and cost a fortune.

The Right Tool for the Job: LangGraph's Store is a Key-Value database. It is designed specifically to hold structured, actionable facts (e.g., {"room": "402", "diet": "vegan"}).

How to store full history: If you ever truly need an AI to semantically search a user's entire multi-year chat history, you do not use the Store. Instead, you save transcripts to a Vector Database and perform a RAG search over their past conversations. For this project, extracting and storing specific facts in the Store is the correct enterprise pattern."""

from pydantic import BaseModel,Field
from typing import Literal

class UserSentiExtraction(BaseModel):
    sentiment:Literal["positive","negative","normal","angry", "frustrated", "disappointed"]=Field(
        description="Analyse the emotional tone of the user's message."
    )
def get_sentiment_node(state:SupportState):
    sentiment_prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert sentiment analyzer and classifier. "
            "Classify the user's emotional tone as positive, negative, normal, "
            "angry, frustrated, or disappointed.",
        ),
        ("human", "{user_query}"),
    ])
    senti_llm=llm.with_structured_output(UserSentiExtraction)
    response_chain=sentiment_prompt | senti_llm
    result=response_chain.invoke({"user_query":state["user_query"]})
    return {
        "sentiment":result.sentiment
    }
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
def generate_response_node(state:SupportState):
    print("------GENERATING NATURAL RESPONSE------")
    #1. Grab the last message/action from your state
    raw_action_result=state["messages"][-1]
    
    #2. Give the LLM its persona instructions
    # Inside your response generation prompt:
    sys_prompt = """
    You are a highly polite, warm, helpful and professional concierge for Novotel.
    The system just processed a request for the user. 
    Here is the raw system data: {raw_data}
    The conversation history for this person is here:{messages}
    Translate this system data into a friendly, natural response to the customer. 
    If a pet-friendly room was booked, enthusiastically mention that their pet is welcome!
    Do not mention 'system data' to the user.
    The user is currently feeling: {sentiment}.
    If they are frustrated or angry, apologize profusely and use a highly empathetic tone.
    Based on the result of their query, and their tone answer accordingly considering you are a hotel concierge. You represent the hotel to the customer.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("human", "{user_query}"),
        # This special placeholder automatically unpacks all previous Human/AI messages
        MessagesPlaceholder(variable_name="messages")
    ])
    
    # 3. Generate the final conversational text
    response_chain = prompt | llm
    final_message = response_chain.invoke({
        "user_query": state["user_query"],
        "raw_data": raw_action_result,
        "sentiment": state["sentiment"],
        "messages":state["messages"]
    })
    
    return {"messages": [final_message]}
from nodes import summarize_conversation_node
def generate_response_node_2(state: SupportState):
    summary = state.get("summary", "No prior context.")
    print("\n========== GENERATE RESPONSE ==========")
    print("Messages:", len(state["messages"]))
    print("Summary:", state.get("summary", "")[:300])
    profile_context = state.get("user_profile", "No profile found.")
    system_instruction = """
    You are a helpful Novotel concierge. 
    Here is what you permanently know about this guest:
    {profile_context}
    
    Use this information to personalize your responses. If they ask something not present in recent messages, 
    check their history to see if you find any information.
    Here is the summary of the conversation so far: {summary}
    
    Answer the user naturally based on the recent messages and the system actions.
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_instruction),
        MessagesPlaceholder(variable_name="messages") # Injects the remaining 4-6 raw messages
    ])
    formatted_prompt = prompt.invoke({
        "summary": summary,
        "messages": state["messages"],
        "profile_context":profile_context
    })

    response = llm.invoke(formatted_prompt)

    return {
        "messages": [response]
    }
    # ... invoke and return ...
from nodes import extract_save_profile_node,load_profile_node 
# 2. Initialize and Wire the Graph
builder = StateGraph(SupportState)

# Add all nodes to the graph
builder.add_node("load_profile",load_profile_node)
builder.add_node("guardrail", guardrail_node)
builder.add_node("hyde_rewriter", hyde_rewriter_node)
builder.add_node("rag_execution", rag_execution_node)
builder.add_node("api_execution", api_node)
builder.add_node("create_booking", create_booking_node)
builder.add_node("cancellation", cancellation_node)
builder.add_node("refusal", refusal_node)
builder.add_node("summarize_messages", summarize_conversation_node)
#builder.add_node("check_history", check_history)
builder.add_node("extract_room_number", extract_room_number_node)
#builder.add_node("validate_room_no", validate_room_number_node)
builder.add_node("extract_order", extract_order_node)
builder.add_node("execute_room_service", execute_room_service_node)
builder.add_node("save_profile",extract_save_profile_node)
builder.add_node("generate_response", generate_response_node_2)
builder.add_node("get_sentiment", get_sentiment_node)
# Add the edges (The Flow)
builder.add_edge(START, "load_profile")
builder.add_edge("load_profile","summarize_messages")
builder.add_edge("summarize_messages","guardrail")

# Add the conditional router
builder.add_conditional_edges(
    "guardrail",
    route_query, 
    {
        "rag": "hyde_rewriter",
        "api": "api_execution",
        "booking": "create_booking",
        "cancel": "cancellation",
        "refusal": "refusal",
        "room_service":"extract_room_number",
        "generate_response":"generate_response"
        
    }
)
builder.add_conditional_edges(
    "extract_room_number",
    validate_room_number_node,{
        "unauthorized-access":"refusal",
        "execute_room_service":"extract_order"
    }
)
builder.add_edge("hyde_rewriter", "rag_execution")
builder.add_edge("rag_execution", "get_sentiment")
builder.add_edge("api_execution", "get_sentiment")
builder.add_edge("create_booking", "get_sentiment")
builder.add_edge("cancellation", "get_sentiment")
builder.add_edge("refusal", "get_sentiment")
builder.add_edge("extract_order","execute_room_service")
builder.add_edge("execute_room_service", "get_sentiment")
#builder.add_edge("check_history", "get_sentiment")
builder.add_edge("get_sentiment","save_profile")
builder.add_edge("generate_response", "save_profile")
builder.add_edge("save_profile",END)


# 3. Compile the application with both short-term and long-term memory.
agent_app = builder.compile(checkpointer=g_checkpointer, store=g_store)
i=agent_app.get_graph().draw_mermaid_png()
with open("agent_app.png", "wb") as f:
    f.write(i)
    

# if __name__ == "__main__":
#     print("Graph Compiled Successfully!")
#     # Let's test a safe RAG query
#     test_state = {
#         #"messages": [HumanMessage(content="How many pet-friendly rooms are available?")],
#         "messages": [HumanMessage(content="Tell me the managers names.")]
        
#     }
#     result = agent_app.invoke(test_state)
#     print("\nFinal Agent Response:\n", result["messages"][-1].content)
    
#     # Run the graph
#     config = {
#             "configurable": {
#                 "thread_id": "chat_001", # This represents the current chat window
#                 "user_id": "alex_123"    # This represents the actual human
#             }
#         }

#     #result = agent_app.invoke(initial_state, config=config)