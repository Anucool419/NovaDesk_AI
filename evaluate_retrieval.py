# evaluate_retrieval.py
import time
import pandas as pd
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# 1. Import your existing vector retriever, LLM, and HyDE chain
# Adjust imports based on where your retriever and llm are defined
from rag import retriever # or from your rag file
from nodes import llm, hyde_chain

# 2. Define standard Query Rewriter Chain (for comparison)
rewrite_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a hotel domain expert. Rewrite the user's question into standard hotel terminology "
               "and policy keywords to optimize search retrieval. Return only the rewritten query."),
    ("human", "{query}")
])
rewriter_chain = rewrite_prompt | llm | StrOutputParser()


# 3. Define the 4 Retrieval Strategy Functions
def run_base_rag(query: str):
    """Direct vector search with the raw query."""
    return retriever.invoke(query)

def run_rewriter_rag(query: str):
    """Rewrite query to formal terms, then retrieve."""
    rewritten_query = rewriter_chain.invoke({"query": query})
    return retriever.invoke(rewritten_query)

def run_hyde_rag(query: str):
    """Generate hypothetical policy document, then retrieve."""
    hypothetical_doc = hyde_chain.invoke({"user_query": query})
    return retriever.invoke(hypothetical_doc)

def run_rewrite_and_hyde(query: str):
    """First rewrite the query, then generate HyDE document, then retrieve."""
    rewritten_query = rewriter_chain.invoke({"query": query})
    hypothetical_doc = hyde_chain.invoke({"user_query": rewritten_query})
    return retriever.invoke(hypothetical_doc)


# 4. Ground Truth Test Dataset (Hotel Policy Scenarios)
# Each query is matched against a distinctive substring from the expected document chunk.
test_dataset = [
                    {
                        "query": "What are the responsibilities of a good guest?",
                        "target": "Guests are expected to behave respectfully toward other guests and hotel employees. Harassment, threats,violence, illegal activity, intentional property damage and serious disturbances are prohibited. "
                    },
                    {
                        "query": "Can I bring my dog?",
                        "target": "Yes you can bring your dog but in designated pet-friendly rooms for an additional fee of $50 per stay. A maximum of two pets is permitted per room. Guests must disclose pets at the time of booking or check-in. Pets must be supervised and must not be left unattended in guest rooms or public areas. If a pet is found unattended, the registered guest may be charged a $100 supervision violation fee, regardless of whether the pet has caused inconvenience, damage or disturbance."
                    },
                    {
                        "query": "What if I get caught puffing a cigarette in my room?",
                        "target": "A cleaning and restoration fee of $250 may be charged when smoking or vaping occurs in a non-smoking room."
                    },
                    {
                        "query": "What time does the pool close?",
                        "target": "The pool closes at 10PM."
                    },
                    {
                        "query": "Can we have a vegan breakfast?",
                        "target": "Yes,  the breakfast buffet includes vegan pastries, plant-based milk and fresh fruit."
                    },
                    {
                        "query":"Do I need my room key to enter the pool area?",
                        "target":"Yes. Guests must present their room key for entry to the rooftop pool area."
                    },
                    {
                        "query":"Are visitors allowed for guests?",
                        "target":"Registered guests are responsible for visitors they invite onto the property. Visitors may be required to register with the front desk and may be subject to identification requirements."
                    },
                    {
                        "query":"What if I lose any item of mine?",
                        "target":"Guests should contact the front desk as soon as possible to report a missing item. The hotel may retain unclaimed items for a limited period before disposal or donation, subject to local requirements."
                    },
                    {
                        "query":"What if I find an item in the hotel?",
                        "target":"Items found on hotel premises are handled according to the property's lost-and-found procedures."
                    },
                    {
                        "query":"Is there Wifi in the hotel rooms?",
                        "target":"Complimentary Wi-Fi is available to registered guests in guest rooms and common areas. Network performance may vary depending on usage, location and service availability. The hotel does not guarantee uninterrupted internet access and is not responsible for loss of data resulting from network interruptions."
                    },
                    {
                        "query":"What is the time upto which we can party at night?",
                        "target":"Quiet hours are observed from 10:00 PM to 7:00 AM. Guests are expected to keep noise at a level that does not disturb other guests. Parties, amplified music and other activities that create excessive noise are not permitted in guest rooms or corridors. "
                    },
                    {
                        "query":"Can we bring our vehicles and park them?",
                        "target":"On-site parking may be available for registered guests, subject to capacity and applicable fees. Parking does not guarantee a reserved space unless explicitly confirmed."    
                        
                    },
                    {
                        "query":"Upto what time can we cancel our booking?",
                        "target":"Standard flexible bookings can be cancelled free of charge up to 24 hours before the scheduled check-in date, unless a different rate-specific policy applies. Cancellations made within 24 hours of arrival may be charged the equivalent of one night's stay plus applicable taxes."    
                    },
                    {
                        "query":"What happens if the customer doesn't show up after booking?",
                        "target":" In the event of a no-show, the hotel may charge one night's accommodation and taxes. Advance-purchase, promotional and non-refundable rates may have different cancellation conditions, which will be displayed at the time of booking."    
                    },
                    {
                        "query":"Can we check-out later or check-in earlier than mentioned time?"
                        ,"target":"Early check-in may be requested and is subject to room availability. Guests arriving before the standard check-in time may store luggage with the front desk. Late check-out can be requested through reception and is subject to availability. A fee may apply depending on the departure time. Guests who retain a room beyond the approved check-out time may be charged an additional night"  
                    }
                ]


# 5. The Core Evaluation Engine (Hit Rate, MRR, Latency)
def evaluate_strategy(strategy_name: str, retrieval_fn, data: list) -> dict:
    total_latency = 0.0
    hits = 0
    mrr_sum = 0.0
    n = len(data)

    print(f"Running evaluation for: {strategy_name}...")

    for item in data:
        start_time = time.time()
        
        # Invoke retrieval strategy
        retrieved_docs = retrieval_fn(item["query"])
        
        end_time = time.time()
        total_latency += (end_time - start_time)

        # Check rankings
        matched = False
        for rank, doc in enumerate(retrieved_docs, start=1):
            if item["target"].lower() in doc.page_content.lower():
                hits += 1
                mrr_sum += (1.0 / rank)
                matched = True
                break

    return {
        "Strategy": strategy_name,
        "Hit Rate (%)": round((hits / n) * 100, 1),
        "MRR (Precision)": round(mrr_sum / n, 3),
        "Avg Latency (s)": round(total_latency / n, 3),
        "Total Hits": f"{hits}/{n}"
    }

# def evaluate_strategy(strategy_name:str,retrieval_fn, data:list):
#     total_latency=0.0
#     hits=0
#     mrr_sum=0
#     n=len(data)
    
    


# 6. Execute and Display Comparison
if __name__ == "__main__":
    strategies = [
        ("Base RAG", run_base_rag),
        ("Query Rewriter", run_rewriter_rag),
        ("HyDE", run_hyde_rag),
        ("Rewriter + HyDE", run_rewrite_and_hyde)
    ]

    results = [
        evaluate_strategy(name, fn, test_dataset)
        for name, fn in strategies
    ]

    df = pd.DataFrame(results)
    print("\n--- RETRIEVAL BENCHMARK REPORT ---")
    print(df.to_string(index=False))
    

# Add this temporary debug block to evaluate_retrieval.py
print("\n--- DIAGNOSTIC: INSPECTING RETRIEVAL MISSES ---")
for item in test_dataset:
    docs = run_base_rag(item["query"])
    combined = " ".join(d.page_content for d in docs).lower()
    
    if item["target"].lower() not in combined:
        print(f"\n[FAILED QUERY]: {item['query']}")
        print(f"[EXPECTED TARGET]: {item['target']}")
        print(f"[TOP CHUNK RETRIEVED]:\n{docs[0].page_content[:750]}...\n" + "-"*40)