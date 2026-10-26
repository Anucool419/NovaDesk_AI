# 🛎️ AI Hotel Concierge (LangGraph + FastAPI)

An enterprise-grade, stateful AI agent built to simulate a virtual hotel front desk. Unlike basic Q&A chatbots, this system bridges the gap between unstructured natural language and strict database transactions, allowing users to query policies, check room availability, book rooms, and request room service seamlessly.

This project demonstrates advanced AI engineering concepts including Agentic Orchestration (LangGraph), Advanced RAG (HyDE & Query Rewriting), State & Memory Management, and Human-in-the-Loop (HITL) security via FastAPI.

## 🏗️ Architecture Overview

The system is broken down into three main layers:

Frontend (Chainlit): Provides a clean, conversational chat UI.

Orchestration Brain (LangGraph): Manages conversation state, memory, guardrails, and decision routing.

Action Execution (FastAPI): Serves as the toolkit for the agent, exposing REST endpoints to interact securely with the SQLite database.

 (Note: Add your Excalidraw diagram here)

 ![Agent Architecture](agent_app.png)

## ✨ Key Features

- Strict Domain Guardrails: A routing node intercepts prompts. If a user asks off-topic questions (e.g., "Write a Python script"), the workflow deflects it immediately, saving tokens and preventing prompt injection.

- Advanced RAG Pipeline: For hotel policy and facility queries, the system uses Query Rewriting to handle multi-part questions and HyDE (Hypothetical Document Embeddings) to improve vector search accuracy. Evaluated using Ragas.

- Stateful Memory: Utilizes LangGraph's short-term and persistent thread memory. The agent remembers dates, names, and room numbers across multiple turns without needing explicit repetition.

- Database Tools via FastAPI: The LLM dynamically extracts parameters from chat to execute API calls (GET /rooms/availability, POST /rooms/book, POST /room-service/order).

- Human-in-the-Loop (HITL) Security: Destructive database actions (like canceling a booking) halt the agent graph. FastAPI enforces Role-Based Access Control (RBAC) via JWTs, requiring an Admin to approve the cancellation before execution.

## 🎥 Live Demo Flow

(Include a GIF or link to your 60-second video demo here)

- Guardrail Test: Rejecting off-topic coding requests.

-  RAG in Action: Answering multi-part policy questions using Query Rewriting and HyDE.

-  Contextual Read/Write: Checking family room availability for "tomorrow" and booking it seamlessly using thread memory.

-  Room Service: Ordering items specifically to the newly booked room.

-  Secure Cancellation: Attempting to cancel a booking triggers the HITL pause, waiting for Admin authorization.


![Agent Architecture](subgraphs/book_g.png)
![Agent Architecture](subgraphs/cancel_g.png)
## 🛠️ Tech Stack

- AI & Orchestration: Python, LangChain, LangGraph, OpenAI / Anthropic APIs

- Backend & API Tools: FastAPI, Pydantic, JWT Authentication

- Database: SQLite (Relational), FAISS (Vector DB for RAG)

- Evaluation: Ragas

- Frontend: Chainlit

## 🚀 Getting Started

Prerequisites

- Python 3.10+

- OpenAI API Key (or equivalent LLM provider)

Installation

Clone the repository:

```
git clone https://github.com/Anucool419/NovaDesk_AI.git
cd NovaDesk_AI
```


Set up a virtual environment:

```
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Install dependencies:

```
pip install -r requirements.txt
```

Environment Variables:
Create a .env file in the root directory and add:

```
OPENAI_API_KEY=your_api_key_here
SECRET_KEY=your_fastapi_jwt_secret
```

Running the Application

Start the FastAPI Backend:
In one terminal, start the tool server:

```
uvicorn main:app --reload --port 8000
```

Start the Chainlit Frontend/Agent:
In a second terminal, launch the UI:

```
chainlit run app.py -w
```

Open http://localhost:8000 in your browser to start chatting!

## 🔮 Future Scope

1. Long-Term Memory: Integrate persistent storage to remember returning guests and their specific preferences across multiple different stays.

2. Modification Subgraph: Add a dedicated workflow to safely handle the complex state transitions required when altering an existing reservation.

3. Multi-Agent Architecture: Transition to a supervisor model that routes tasks to specialized, independent sub-agents (e.g., a dedicated Room Service Agent and a Booking Agent).

4. Voice-Based Interactions: Integrate speech-to-text capabilities to allow hands-free, natural spoken conversations with the virtual front desk.

## 🤝 Let's Connect

I'm documenting the build process and architectural decisions of this project on my DEV Community blog, AI Foundry.

[Read my deep-dive articles here](https://dev.to/zeroshotanu/) | Connect on LinkedIn [![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://www.linkedin.com/in/ananya-s-6b300527a/)
