from langgraph.store.memory import InMemoryStore

# 1. We mock the exact function we just wrote
from datetime import datetime

def save_profile_node(state: dict, config: dict, store: InMemoryStore):
    user_id = config['configurable'].get("user_id", "anonymous_guest")
    namespace = ("users", user_id)
    
    existing_entry = store.get(namespace, "profile")
    profile = existing_entry.value if existing_entry else {
        "traits": {}, "active_state": {}, "history": []
    }
    
    new_pref = state.get("preferences") 
    if new_pref:
        new_confidence = 1.0 
        existing_pref = profile["traits"].get("preferences", {})
        existing_confidence = existing_pref.get("confidence_score", 0.0)
        
        if new_confidence >= existing_confidence:
            profile["traits"]["preferences"] = {
                "content": new_pref,
                "confidence_score": new_confidence,
                "timestamp": datetime.now().isoformat()
            }

    extracted_items = state.get("extracted_items")
    if extracted_items:
        profile["history"].append({
            "memory_type": "room_order",
            "content": extracted_items,
            "timestamp": datetime.now().isoformat()
        })
        
    store.put(namespace, "profile", profile)
    return {}

# 2. Set up our dummy variables
mock_store = InMemoryStore()
mock_config = {"configurable": {"user_id": "guest_chirag_123"}}

# 3. Simulate the data returning from the subgraph
mock_state = {
    "preferences": "Allergic to peanuts, needs high floor",
    "extracted_items": "2 Club Sandwiches, 1 Diet Coke"
}

# 4. Execute the node
save_profile_node(mock_state, mock_config, mock_store)

# 5. Fetch the result and print the JSON
saved_memory = mock_store.get(("users", "guest_chirag_123"), "profile")

import json
print(json.dumps(saved_memory.value, indent=2))