
from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class SupportState(TypedDict):
    # add_messages acts as a reducer, appending new messages to the existing list rather than overwriting
    messages:Annotated[List[BaseMessage], add_messages]
    
    #ORiginal question
    user_query:str
    
    #Output of our query rewriter/HyDE
    transformed_query:Optional[str]
    
    # A flag to determine if the query passed our guardrails (True/False)
    is_safe:bool
    
    # A string telling our router which path to take ("rag", "api", "booking" or "refusal")
    route_decision:str
    
    #Room number to keep in our memory
    room_number:Optional[int] # Injected by the Store (if it exists)
    extracted_items: List[str]      # The food the LLM extracted
    sentiment:str
    summary:str #NEW: Holds the rolling conversation summary
    user_profile: dict #holds cross section permanent facts.
    preferences:str
    name:Optional[str]
    email:Optional[str]
    check_in:Optional[str]
    check_out:Optional[str]
    room_type:Optional[str]
    guest_id:Optional[int]
    room_id:Optional[int]
    retrieved_contexts:Optional[list[str]]
class BookingState(TypedDict, total=False): #what is total=false
    user_query:str
    user_response:Optional[str]
    name:Optional[str]
    email:Optional[str]
    check_in:Optional[str]
    check_out:Optional[str]
    room_type:Optional[str]
    guests:Optional[str]
    guest_id:Optional[int]
    room_id:Optional[int]
    missing_fields:list[dict]
    preferences:Optional[str]
    available_room:Optional[dict]
    response:Optional[str]
    messages:Annotated[List[BaseMessage], add_messages]
    
from typing import TypedDict, Optional, Literal
from datetime import date

class CancellationState(TypedDict):

    user_id: int
    user_query:str
    booking_id: int
    role:Literal["admin","guest"]
    reason: str
    missing_fields:list[dict]
    booking: Optional[dict]
    current_date:date
    booking_name:str
    refund_amount: Optional[float]
    is_verified:bool
    cancellation_request_id: Optional[str]

    admin_id: Optional[str]

    approval_status: Optional[str]

    cancellation_result: Optional[dict]
    messages:str

    error: Optional[str]
