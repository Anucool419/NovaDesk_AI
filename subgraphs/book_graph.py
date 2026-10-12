from langgraph.graph import StateGraph,START,END
from state import BookingState
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain.chat_models import init_chat_model
from pydantic import BaseModel,Field
from typing import Optional
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
os.environ["OPENAI_API_KEY"]=os.getenv("OPENAI_API_KEY")

llm=init_chat_model("openai:gpt-4o-mini", temperature=0) 
from datetime import date


"""Alternative Recommendations & Budget Logic: 
Shelve these for now. If a pet-friendly room isn't available, your API should simply return "No pet-friendly rooms available for these dates." 
The main LLM will naturally read this API response and ask the user, "I couldn't find a pet-friendly room. Would you like me to check standard 
rooms instead?" Rely on the LLM's conversational reasoning rather than hardcoding complex recommendation algorithms into your graph."""

class BookDetails(BaseModel):
    name:Optional[str]=Field(description="Name of guest", default=None)
    #check_in_date:Optional[str]=Field(description="Date of check-in",default=None)
    #check_out_date:Optional[str]=Field(description="Date of check out", default=None)
    email:Optional[str]=Field(description="Email of guest", default=None)
    preferences:Optional[str]=Field(description="Any other preferences of the guest like pet friendly room, or sea facing room, or Family Room", default=None)
    room_type: str | None = Field(default=None,description="Requested room type such as standard, deluxe, suite, family room, etc.")
    check_in_date: date | None = None
    check_out_date: date | None = None
book_llm=llm.with_structured_output(BookDetails)   

def extract_details_node(state:BookingState)->BookingState:
    '''Extract given details from the query'''
    from langchain_core.prompts import ChatPromptTemplate
    
    q=state.get("user_response") or state['user_query'] 
    current_date = date.today().isoformat()
    
    extraction_prompt = ChatPromptTemplate.from_messages([
        ("system", f"""
        You are a hotel booking detail extractor.

        Extract only information explicitly provided by the user.
        Do not invent missing information.
        Return null for missing fields.

        Today's date is {current_date}.
        Resolve relative dates such as "today" and "tomorrow" using today's date.
        Return check-in and check-out dates as ISO dates in YYYY-MM-DD format.
    """),
        ("human", "{user_query}")
    ])
    
    extraction_chain = extraction_prompt | book_llm
    extractor = extraction_chain.invoke({"user_query": q})
    if extractor.name is not None: # This is because let's say the name field had been added in the previous conversation, it should not get overriden.
        state["name"] = extractor.name

    if extractor.email is not None:
        state["email"] = extractor.email

    if extractor.check_in_date is not None:
        state["check_in"] = extractor.check_in_date

    if extractor.check_out_date is not None:
        state["check_out"] = extractor.check_out_date

    if extractor.preferences is not None:
        state["preferences"] = extractor.preferences
    if extractor.room_type is not None:
        state["room_type"] = extractor.room_type

    return state

REQUIRED_FIELDS=[
    "name",
    "email",
    "check_in",
    "check_out"
]

def validate_details_node(state:BookingState)->BookingState:
    missing=[]
    
    for field in REQUIRED_FIELDS:
        value=state.get(field)
        
        if value is None or not str(value).strip():
            missing.append(field)
    
    state["missing_fields"]=missing
    return state

def router_after_validation(state:BookingState):
    if state.get("missing_fields") and len(state['missing_fields'])>0:
        return "missing"
    else:
        return "complete"

from langgraph.types import interrupt, Command
def ask_for_missing_node(state:BookingState):
    missing=state.get("missing_fields",[])
    if not missing:
        return {"response":"All required fields are present."}
    prompt="I still require the following details: " + ", ".join(missing)
    user_input = interrupt({"question":prompt})
    if not isinstance(user_input, dict) or not user_input.get("user_input"):
        return {"response": "Please provide the missing booking details."}
    return {"user_response": user_input["user_input"]}
   
from api_tools import check_room_availability
def check_availability_node(state:BookingState):
    print("----CHECK AVAILABILITY NODE CALLED----")
    check_in = state["check_in"]
    check_out = state["check_out"]

    result = check_room_availability.invoke({
        "check_in_date": check_in,
        "check_out_date": check_out
    })

    return {
        "available_room": result,
        "response": result
    }
from api_tools import get_or_create_guest
def find_or_create_guest_node(state:BookingState):
    print("----FIND OR CREATE GUEST----")
    guest = get_or_create_guest.invoke(
        {
            "name":state["name"],
            "email":state["email"]
        }
    )
    if "error" in guest:
        return {"response":guest["error"]}
    state["guest_id"]=guest["id"]
    return state

from api_tools import find_available_room
# def find_available_room_node(state:BookingState):
#     print("---FIND AVAILABLE ROOM----")
#     room = find_available_room.invoke({
#         "check_in_date": state["check_in"],
#         "check_out_date": state["check_out"],
#         "room_type": state.get("room_type")
#     })
#     print("ROOM RESULT:", room)
#     print("ROOM TYPE:", type(room))
#     # Handle error string responses
#     if isinstance(room, str):
#         return {"response": room}
    
#     # Handle error dict responses
#     if isinstance(room, dict) and "error" in room:
#         return {"response": room["error"]}
    
#     # Handle successful dict response
#     if isinstance(room, dict) and "id" in room:
#         state["room_id"] = room["id"]
#         return state
    
#     # If we got here, something unexpected happened
#     return {"response": "No room available for the requested dates."}

def find_available_room_node(state: BookingState):
    print("---FIND AVAILABLE ROOM----")

    available_rooms = state.get("available_room", [])
    requested_type = state.get("room_type")

    print("AVAILABLE ROOMS:", available_rooms)
    print("REQUESTED TYPE:", requested_type)

    if not available_rooms:
        return {
            "response": "No rooms are available for the requested dates."
        }

    if requested_type:
        normalized_type = requested_type.lower().replace(" room", "").strip()
        matching_rooms = [
            room for room in available_rooms
            if normalized_type in room["room_type"].lower()
        ]
    else:
        matching_rooms = available_rooms

    if not matching_rooms:
        return {
            "response": f"No {requested_type} room is available for those dates."
        }

    selected_room = matching_rooms[0]

    return {
        "room_id": selected_room["id"]
    }





from api_tools import book_room    
def create_booking_node(state:BookingState):
    print("___CREATING BOOKING NODE____")
    
    # Guard: ensure both guest_id and room_id are present
    if "guest_id" not in state or not state.get("guest_id"):
        return {"response": "Error: Guest ID not resolved. Cannot proceed with booking."}
    
    if "room_id" not in state or not state.get("room_id"):
        return {"response": "Error: Room ID not resolved. Cannot proceed with booking."}
    
    payload={
        "guest_id":state["guest_id"],
        "room_id":state["room_id"],
        "check_in_date":state["check_in"].isoformat(),
        "check_out_date":state["check_out"].isoformat(),
        "special_requests": state.get("preferences")
    }
    
    result=book_room.invoke({"booking": payload})
    # FIX: Explicitly return the fields to force them into the parent SupportState.
    # We map 'room_id' to 'room_number' so the ROOM_SERVICE node can find it.
    return {
        "response": result,
        "guest_id": state["guest_id"],
        "room_number": int(state["room_id"]), 
        "check_in": state["check_in"],
        "check_out": state["check_out"]
    }

workflow=StateGraph(BookingState)
workflow.add_node("extract_details", extract_details_node)
workflow.add_node("validate_details", validate_details_node)
workflow.add_node("ask_missing", ask_for_missing_node)
workflow.add_node("check_available", check_availability_node)
workflow.add_node("find_or_create_guest", find_or_create_guest_node)
workflow.add_node("find_room", find_available_room_node)
workflow.add_node("create_booking", create_booking_node)

workflow.add_edge(START, "extract_details")
workflow.add_edge("extract_details", "validate_details")
workflow.add_conditional_edges(
    "validate_details",
    router_after_validation,
    {
        "missing": "ask_missing",
        "complete": "check_available"
    }
)
workflow.add_edge("ask_missing", "extract_details")
workflow.add_edge("check_available", "find_or_create_guest")
workflow.add_edge("find_or_create_guest", "find_room")
workflow.add_edge("find_room", "create_booking")
workflow.add_edge("create_booking", END)


from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver() # MEmory is important as once ask_node implements interrupt() tha existing state details even in extract is erased.

booking_app = workflow.compile(
    checkpointer=checkpointer
)

#booking_app = workflow.compile()

i=booking_app.get_graph().draw_mermaid_png()
with open("book_g.png", "wb") as f:
    f.write(i)


if __name__ == "__main__":
    config={"configurable":{"thread_id":"book-test-2"}}
    state = {"user_query": "Book a Executive Suite room Sept 12-15"}
    
    print("Starting with incomplete data...")
    result = booking_app.invoke(state, debug=True, config=config)
    #print("\nInterrupted. Missing:", result.get("missing_fields"))
    #print("Question:", result.get("__interrupt__")[0].value if result.get("__interrupt__") else "No interrupt")
    
    # Resume with complete info
    print("\n\nResuming with complete info...")
    #state["user_query"] = "My name is John Doe, email is john@example.com, book a deluxe room from Sept 3 to Sept 5"
    #result = booking_app.invoke(state, debug=True, config=config)
    result = booking_app.invoke(
            Command(
                resume={
                    "user_input": "My name is James Doe, email is jamd@example.com"
                }
            ),
            config=config
        )
    print("\n\nFinal Result:", result.get("response"))