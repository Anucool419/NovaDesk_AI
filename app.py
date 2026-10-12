import chainlit as cl
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from graph import agent_app
import uuid
import textwrap

# Non-blocking async wrapper for LangGraph invoke
async_invoke = cl.make_async(agent_app.invoke)

@cl.on_chat_start
async def start_chat():
    logo = cl.Image(path="public/logo.webp", name="logo", display="inline")
    cl.user_session.set("thread_id", str(uuid.uuid4()))
    cl.user_session.set("user_id", "guest_alex") 
    
    await cl.Message(content="", elements=[logo]).send()
    
    content = textwrap.dedent("""# NOVA PARADISE HOTEL
### Your Personal AI Concierge
I can help you with:
- Room booking and cancellations
- Room service
- Room availability information
- Other hotel policy questions.""")
    
    await cl.Message(content=content).send()

async def process_state_after_run(result, config):
    """Handles the graph output, checking if it finished or paused at an interrupt."""
    while True:
        new_state = agent_app.get_state(config)
        
        # Case 1: Graph finished completely (no active interrupts)
        if not (new_state.tasks and new_state.tasks[0].interrupts):
            
            # --- THE FIX: Pull the final message directly from the graph's ultimate state ---
            messages = new_state.values.get("messages", [])
            
            if messages:
                final_response = messages[-1]
                response_text = final_response.content if hasattr(final_response, "content") else str(final_response)
            else:
                response_text = "Task completed successfully."
                
            await cl.Message(content=response_text).send()
            return

        # Case 2: Graph is paused at an interrupt
        interrupt_value = new_state.tasks[0].interrupts[0].value
        
        # Display the question/PIN request to the user
        question = interrupt_value.get("question", "Please provide the missing details:")
        await cl.Message(content=question).send()
        
        # Stop the while loop and wait for the user to type in the Chainlit UI
        return


@cl.on_message
async def main(message: cl.Message):
    thread_id = cl.user_session.get("thread_id")
    user_id = cl.user_session.get("user_id")
    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}
    
    # Optional: Display a loading spinner in the UI while the AI is thinking
    async with cl.Step(name="Nova Concierge", type="run") as step:
        # 1. CHECK PREVIOUS STATE
        graph_state = agent_app.get_state(config)
        
        if graph_state.tasks and graph_state.tasks[0].interrupts:
            # Resume the graph using their new message
            result = await async_invoke(
                Command(resume={"user_input": message.content}), 
                config=config
            )
        else:
            # The graph is not paused. This is a brand new request.
            initial_state = {
                "user_query": message.content,
                "messages": [HumanMessage(content=message.content)],
            }
            result = await async_invoke(initial_state, config=config)
            
        step.output = "Processed request."
    
    # 2. CHECK NEW STATE AFTER RUNNING AND PRINT THE UI MESSAGES
    await process_state_after_run(result, config)