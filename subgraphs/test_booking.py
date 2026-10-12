from subgraphs.book_graph import booking_app
from langgraph.types import Command

config = {
    "configurable": {
        "thread_id": "booking-test-1"
    }
}

# Test 1: Incomplete booking - should trigger interrupt
incomplete_query = "I want to book a Family room from 3rd Oct to 7th Oct 2026"

print("=" * 60)
print("TEST: Incomplete booking request")
print("=" * 60)
print(f"Query: {incomplete_query}\n")

state = booking_app.invoke({"user_query": incomplete_query}, config=config)
print(f"Missing fields: {state.get('missing_fields')}")
if state.get("__interrupt__"):
    interrupt_data = state["__interrupt__"][0]

    print(f"Graph interrupted: {interrupt_data.value}\n")

    #print(f"Graph interrupted: {state['__interrupt__'][0].value}\n")
    
    # Get user input and resume
    user_response = input("Provide missing details (name and email): ")
    
    # Clear interrupt flag before resuming
    #state.pop("__interrupt__", None)
    #state["user_query"] = user_response
    
    print(f"\nResuming with: {user_response}\n")
    state = booking_app.invoke(
        Command(
            resume={
                "user_input": user_response
            }
        ),
        config=config
    )

    print(f"\nFinal Result: {state.get('response')}")
    #state = booking_app.invoke(state, debug=True)
    #print(f"\nFinal Result: {state.get('response')}")

print("\n" + "=" * 60)
print("TEST: Complete booking request")
print("=" * 60)

# Test 2: Complete booking info - should go through end-to-end
# complete_query = "Book a Family room from Sept 3 to Sept 5 for Jane Smith with email jane@example.com"

# print(f"Query: {complete_query}\n")

# state = booking_app.invoke({"user_query": complete_query}, debug=True)
# print(f"\nResult: {state.get('response')}")
