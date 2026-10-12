from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
os.environ["OPENAI_API_KEY"]=os.getenv("OPENAI_API_KEY")

llm=init_chat_model("openai:gpt-4o-mini")

from state import CancellationState
from api_tools import (
    check_cancellation_booking,
    create_cancellation_request,
    decide_cancellation,
)

from datetime import date
class CancelDetails(BaseModel):
    booking_id: int | None = Field(
        default=None,
        description="The booking ID explicitly provided by the user. Return null if missing.",
    )
    guest_name: str | None = Field(default=None, description="Name of guest on the booking.")
    reason: str | None = Field(default=None, description="Reason for cancellation.")

current_date = date.today().isoformat()

def extract_details_node(state:CancellationState)->CancellationState:
    """Extract details from user query."""
    print("-----Extracting details-------")
    q=state.get("user_query") or state['user_query']
    from langchain_core.prompts import ChatPromptTemplate
    cancel_prompt=ChatPromptTemplate.from_messages([
        ("system", """You are a details extractor. Given the user prompt, extract the details from it.Do not create your own information. Strictly, use the information given in the prompt.
        Today's date is {current_date}.
        Resolve relative dates such as "today" and "tomorrow" using today's date.
        Return check-in and check-out dates as ISO dates in YYYY-MM-DD format."""),
        ("human", "{user_query}")
    ])
    cancel_llm=llm.with_structured_output(CancelDetails)
    cancel_chain=cancel_prompt | cancel_llm
    extractor=cancel_chain.invoke({"user_query":q, "current_date":current_date})
    
    if extractor.booking_id is not None:
        state["booking_id"]=extractor.booking_id
    if extractor.guest_name is not None:
        state['booking_name']=extractor.guest_name
    state['current_date']=current_date
    if extractor.reason is not None:
        state['reason']=extractor.reason
    return state

REQUIRED_FIELDS=[
    "booking_name", "booking_id", "reason"
]

def validate_details_node(state:CancellationState)->CancellationState:
    print("-----Validating if there is missing info------")
    missing=[]
    for f in REQUIRED_FIELDS:
        value=state.get(f)

        if f == "booking_id":
            missing_value = not isinstance(value, int) or value <= 0
        else:
            missing_value = value is None or not str(value).strip()

        if missing_value:
            missing.append(f)
    state['missing_fields']=missing
    return state

def router_after_validation(state:CancellationState)->str:
    if state.get("missing_fields") and len(state['missing_fields'])>0:
        return "missing"
    else:
        return "complete"
    
from langgraph.types import interrupt,Command
def asking_for_missing_node(state:CancellationState)->CancellationState:
    print("_____Asking for missing info____")
    missing=state.get("missing_fields",[])
    if not missing:
        return {"response":"All required fields are present."}
    field_names = {
        "booking_id": "the booking ID",
        "booking_name": "the guest name on the booking",
        "reason": "the cancellation reason",
    }
    requested_details = [field_names.get(field, field) for field in missing]
    prompt="I still require: " + ", ".join(requested_details) + "."
    user_input = interrupt({"question":prompt})
    if not isinstance(user_input, dict) or not user_input.get("user_input"):
        return {"error": "Missing-details response must contain user_input."}
    return {"user_query": user_input["user_input"]}

def verify_booking_node(state:CancellationState)->CancellationState:
    print("----Ensuring booking id exists......")
    result = check_cancellation_booking.invoke({
        "booking_id": state["booking_id"],
        "guest_name": state["booking_name"],
    })

    if "error" in result:
        return {"is_verified": False, "error": result["error"]}
    if not result.get("can_cancel", False):
        return {"is_verified": False, "error": "This booking cannot be cancelled."}

    return {"is_verified": True, "booking": result}

def create_request_node(state:CancellationState)->CancellationState:
    print("----Creating cancellation request----")
    result = create_cancellation_request.invoke({
        "booking_id": state["booking_id"],
        "guest_name": state["booking_name"],
        "cancellation_reason": state["reason"],
    })

    if "error" in result:
        return {"error": result["error"]}
    return {"cancellation_request_id": str(result["id"])}
    
    
def admin_approval_node(state:CancellationState)->CancellationState:
    print("------CHECKING RBAC PERMISSIONS-----")
    
    if not state.get("is_verified") or state.get("error"):
        return state

    
    # 1. Ask for a PIN in the chat so a recruiter can actually test it
    admin_decision = interrupt({
        "type": "text_input", 
        "question": (
            f"🛎️ **[MANAGER APPROVAL REQUIRED]**\n"
            f"Cancellation Request ID: {state['cancellation_request_id']}\n"
            f"*(Portfolio Demo: Type the Manager PIN '9999' to approve, or anything else to reject)*"
        )
    })

    # 2. Extract the text the user typed in Chainlit
    user_input = str(admin_decision.get("user_input", "")).strip()

    # 3. Handle the PIN simulation
    if user_input == "9999":
        decision = "approved"
        admin_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzkxMzk2NDUwfQ.gjFxNnYwKoJ9pCUpy1ACbAQ0Jub-Nve64sQXlLOEkoY"  # Fake token to satisfy your backend
    else:
        decision = "rejected"
        admin_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzkxMzk2NDUwfQ.gjFxNnYwKoJ9pCUpy1ACbAQ0Jub-Nve64sQXlLOEkoY"
    
    #THis was for backend approval using FastAPI docs. Above shows in the UI.
    
    # admin_decision = interrupt({
    #         "cancellation_request_id": state["cancellation_request_id"],
    #         "booking_id": state["booking_id"],
    #         "reason": state["reason"],
    #         "message": "An authenticated admin must approve or reject this request.",
    #     })
    
    # if not isinstance(admin_decision, dict):
    #     return {"error": "Admin decision must include decision and admin_token."}

    # decision = str(admin_decision.get("decision", "")).strip().lower()
    # decision = {"approve": "approved", "reject": "rejected"}.get(decision, decision)
    # admin_token = str(admin_decision.get("admin_token", "")).strip() #remove extra whitespaces around admin_token (JWT)
    # if decision not in {"approved", "rejected"} or not admin_token:
    #     return {"error": "Valid admin decision and admin token are required."}

    result = decide_cancellation.invoke({
        "request_id": int(state["cancellation_request_id"]),
        "decision": decision,
        "admin_token": admin_token,
        "admin_note": admin_decision.get("admin_note"),
    })
    if "error" in result:
        return {"error": result["error"]}
    return {"approval_status": result.get("status"), "cancellation_result": result}

def execute_cancel_node(state:CancellationState)->CancellationState:
    # 1. Handle the error case
    error_val = state.get("error")
    if error_val or state['approval_status'].lower()=="rejected":
        
        fail_reason = error_val if error_val else "Invalid PIN. Authorization denied by management."
        error_msg = f"❌ **Cancellation Failed:** {fail_reason}"
        return {
            "response": fail_reason,
            "messages": [AIMessage(content=error_msg)]
        }
    else:
        # 2. Handle the success case
        success_msg = (
            "✅ **Cancellation Confirmed!**\n\n"
            "Your booking has been successfully cancelled by management, and any applicable "
            "refunds have been processed. Is there anything else I can assist you with today?"
        )
        
        return {
            "response": state.get("cancellation_result", "Cancellation request processed."),
            "messages": [AIMessage(content=success_msg)]
        }

def route_after_verification(state:CancellationState)->str:
    if state.get("error") or not state.get("is_verified"):
        return "failed"
    return "verified"
    
    
workflow=StateGraph(CancellationState)
workflow.add_node("extract", extract_details_node)
workflow.add_node("validate", validate_details_node)
workflow.add_node("ask_missing", asking_for_missing_node)
workflow.add_node("verify_booking", verify_booking_node)
workflow.add_node("admin_approval", admin_approval_node)
workflow.add_node("execute_cancel", execute_cancel_node)
workflow.add_node("create_request", create_request_node)
workflow.add_edge("extract","validate")
workflow.add_conditional_edges(
    "validate",
    router_after_validation,{
        "missing":"ask_missing",
        "complete":"verify_booking"
    }
)
workflow.add_edge("ask_missing","extract")
workflow.add_conditional_edges(
    "verify_booking",
    route_after_verification,{
        "verified":"create_request",
        "failed":END
    }
)

workflow.add_edge("create_request","admin_approval")
workflow.add_edge("admin_approval","execute_cancel")
workflow.add_edge("execute_cancel",END)
workflow.add_edge(START,"extract")

checkpointer = MemorySaver()
cancel_subgraph=workflow.compile(checkpointer=checkpointer)

i=cancel_subgraph.get_graph().draw_mermaid_png()
with open("cancel_g.png", "wb") as f:
    f.write(i)

     
        
    
if __name__ == "__main__":
    thread_config = {"configurable": {"thread_id": "guest_session_001"}}
    
    # 1. ACT AS THE GUEST
    print("\n[GUEST] Initiating cancellation...")
    initial_state = {
        "role": "guest",
        "user_query": "Cancel booking 4 for John Doe because my plans changed.",
    }
    
    # Run the graph. It will execute extract -> verify -> and pause at approval
    for chunk in cancel_subgraph.stream(initial_state, thread_config):
        print(chunk)
        
    print("\n--- GRAPH IS PAUSED ---")
    
    # 2. ACT AS THE ADMIN
    print("\n[ADMIN DASHBOARD]")
    # The terminal will wait for your input here
    decision = input("Type approve or reject: ").strip().lower()
    admin_token = input("Paste the admin JWT: ").strip()
    admin_note = input("Admin note (optional): ").strip() or None
    
    # 3. WAKE THE GRAPH UP
    # We pass the decision back into the graph using Command
    print("\n[SYSTEM] Resuming graph with admin decision...")
    resume_payload = {
        "decision": decision,
        "admin_token": admin_token,
        "admin_note": admin_note,
    }
    for chunk in cancel_subgraph.stream(
        Command(resume=resume_payload),
        thread_config,
    ):
        print(chunk)
            

    