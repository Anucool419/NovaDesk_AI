from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.config import RunnableConfig
from langchain_core.tools import tool
from langchain_core.messages import AIMessage
from state import SupportState
from rag import retriever,llm
# =====================================================================
# 1. RETRIEVAL & GENERATION HELPERS
# =====================================================================
@tool
def search_hotel_policies(query: str) -> str:
    """
    Use this tool to answer guest questions about hotel policies, 
    such as pool hours, pet rules, check-in times, or cancellation policies.
    """
    results = retriever.invoke(query)
    
    return "\n\n".join(doc.page_content for doc in results)


policy_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are a precise and professional hotel customer support agent. "
        "Answer the guest's question using ONLY the provided hotel policy context. "
        "CRITICAL INSTRUCTION:\n"
        "1. State exact fees, prices, times, and rules mentioned in the context. Never invent numbers.\n"
        "2. DEDUCTIVE REASONING ALLOWED: Apply the rules and operating hours in the context to the guest's specific scenario "
        "(for example, if the guest asks about visiting at 2:00 AM and the context states hours are 6:00 AM to 10:00 PM, explicitly say 'No' and state the operating hours).\n"
        "3. MULTI-PART QUESTIONS: If a question has multiple parts, answer every part supported by the context by combining the relevant rules.\n"
        "4. Only say 'I do not know' if the retrieved context is completely unrelated to the guest's inquiry.\n\n"
        "Context:\n{context}",
        
    ),
    ("human", "{question}"),
])

policy_chain = policy_prompt | llm | StrOutputParser()


def answer_policy_question(search_query: str, original_question: str = None) -> tuple[str, list[str]]:
    """
    Retrieves relevant policy chunks using `search_query` (Naive, Rewritten, or HyDE),
    and answers the guest's `original_question`.
    Returns: (answer_str, raw_chunks_list)
    """
    if original_question is None:
        original_question = search_query

    # Fetch raw Document objects directly from retriever so we keep the list[str] for RAGAS
    docs = retriever.invoke(search_query)
    raw_chunks = [doc.page_content for doc in docs]
    context_str = "\n\n".join(raw_chunks)

    print(f"\n[DEBUG - RETRIEVED {len(raw_chunks)} CHUNKS]:\n{context_str}\n")

    # CRITICAL: Always pass the user's ORIGINAL question to the answer generator,
    # NOT the fake HyDE paragraph!
    answer = policy_chain.invoke({
        "context": context_str,
        "question": original_question
    })
    return answer, raw_chunks


# =====================================================================
# 2. QUERY TRANSFORMATION CHAINS (HYDE & QUERY REWRITER)
# =====================================================================
# Mode A: HyDE Prompt (Generates a formal hypothetical policy paragraph)
hyde_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert at writing formal hotel policy documents. "
               "The user will ask a question. Write a short, single-paragraph hypothetical hotel policy "
               "that perfectly answers their question. Use professional, legal hospitality terminology."),
    ("human", "{user_query}")
])
hyde_chain = hyde_prompt | llm | StrOutputParser()

# Mode B: Query Rewriter Prompt (Strips conversational noise into keywords)
rewriter_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert search query optimizer for a hotel policy database. "
               "Rewrite the guest's message into a short, direct, keyword-focused search query. "
               "Strip out all personal backstory, names, and conversational filler. "
               "If the question has multiple parts, include keywords for all parts."),
    ("human", "{user_query}")
])
rewriter_chain = rewriter_prompt | llm | StrOutputParser()


# =====================================================================
# 3. LANGGRAPH NODES (WITH DYNAMIC RAG_MODE SWITCH)
# =====================================================================
def hyde_rewriter_node(state: SupportState, config: RunnableConfig):
    """
    Dynamically switches between 'naive', 'rewriter', and 'hyde' based on config.
    Defaults to 'hyde' when running normally in Chainlit.
    """
    rag_mode = config.get("configurable", {}).get("rag_mode", "hyde")
    user_query = state["user_query"]

    print(f"---NODE: PRE-RETRIEVAL (MODE: {rag_mode.upper()})---")

    if rag_mode == "naive":
        # No LLM call! Directly pass the raw user query to FAISS (0 extra latency/tokens)
        transformed_query = user_query

    elif rag_mode == "rewriter":
        # Fast LLM call: strips noise into a clean search query
        transformed_query = rewriter_chain.invoke({"user_query": user_query})

    else:  # Default: "hyde"
        # Full HyDE LLM call: writes a hypothetical policy paragraph
        transformed_query = hyde_chain.invoke({"user_query": user_query})

    print(f"Original Query: {user_query}")
    print(f"Transformed Query ({rag_mode}): {transformed_query}")

    return {"transformed_query": transformed_query}


def rag_execution_node(state: SupportState):
    """
    Executes vector search using `transformed_query`, generates the final response
    against `user_query`, and saves `retrieved_contexts` for RAGAS evaluation.
    """
    print("---NODE: RAG EXECUTION---")
    user_query = state["user_query"]
    search_query = state.get("transformed_query") or user_query

    answer, raw_chunks = answer_policy_question(
        search_query=search_query,
        original_question=user_query
    )

    return {
        "messages": [AIMessage(content=answer)],
        "retrieved_contexts": raw_chunks,  # <-- Read by run_ablation.py!
    }