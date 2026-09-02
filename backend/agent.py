from __future__ import annotations

import os
import sqlite3
from typing import Annotated, List, TypedDict, Union

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from mem0 import MemoryClient
from pydantic import BaseModel

# ============================================================
# 1. ENVIRONMENT CONFIGURATION
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MEM0_API_KEY = os.getenv("MEM0_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not MEM0_API_KEY:
  raise ValueError("MEM0_API_KEY is missing from your .env file.")

if not GROQ_API_KEY and not OPENAI_API_KEY:
  raise ValueError(
      "Either GROQ_API_KEY or OPENAI_API_KEY must be provided in .env."
  )


# ============================================================
# 2. INITIALIZE SERVICES & FASTAPI
# ============================================================

app = FastAPI(title="Leo AI Assistant API")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        FRONTEND_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Primary model: Groq
groq_llm = None
if GROQ_API_KEY:
  groq_llm = ChatGroq(
      model="openai/gpt-oss-120b",
      temperature=0.7,
      groq_api_key=GROQ_API_KEY,
  )

# Fallback model: OpenAI
openai_llm = None
if OPENAI_API_KEY:
  openai_llm = ChatOpenAI(
      model="gpt-4o-mini",
      temperature=0.7,
      api_key=OPENAI_API_KEY,
  )

m_client = MemoryClient(api_key=MEM0_API_KEY)


# ============================================================
# 3. LANGGRAPH STATE DEFINITION
# ============================================================


class State(TypedDict):
  messages: Annotated[List[Union[HumanMessage, AIMessage]], add_messages]
  user_id: str


# ============================================================
# 4. MEM0 - MEMORY RETRIEVAL & PERSISTENCE
# ============================================================


def get_relevant_memory(query: str, user_id: str) -> str:
  try:
    response = m_client.search(query, filters={"user_id": user_id})

    if isinstance(response, dict):
      memories = response.get("results", [])
    else:
      memories = response

    if not memories:
      return "No prior memories for this user."

    memory_text = []
    for memory in memories:
      if not isinstance(memory, dict):
        continue
      text = memory.get("memory", "")
      if text:
        memory_text.append(f"- {text}")

    if not memory_text:
      return "No relevant memories found."

    return "\n".join(memory_text)

  except Exception as e:
    print(f"\n[Memory retrieval warning] {e}\n")
    return "Memory system temporarily unavailable."


def update_memory(user_id: str, user_msg: str, ai_msg: str):
  try:
    messages = [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": ai_msg},
    ]
    m_client.add(messages, user_id=user_id)
  except Exception as e:
    print(f"\n[Memory update warning] {e}\n")


# ============================================================
# 5. CHATBOT NODE & INFERENCE ENGINE
# ============================================================


def chatbot_node(state: State):
  user_id = state["user_id"]
  latest_message = state["messages"][-1]
  latest_query = str(latest_message.content)

  memory_context = get_relevant_memory(latest_query, user_id)

  system_prompt = f"""You are Leo, a helpful personal AI assistant.
Your job is to assist the user naturally and intelligently.
You have access to long-term memories about the user.
Use memories ONLY when they are relevant to the current conversation.
Do NOT invent memories.
If a memory is uncertain or unrelated, ignore it.
Be conversational, concise, and helpful.

Relevant User Memories:
{memory_context}
"""

  messages_for_llm = [SystemMessage(content=system_prompt)] + list(
      state["messages"]
  )

  ai_response_text = ""

  # Attempt inference via Groq first
  if groq_llm:
    try:
      response = groq_llm.invoke(messages_for_llm)
      ai_response_text = response.content
    except Exception as e:
      print(f"\n[Groq LLM Warning] {e}. Falling back to OpenAI...\n")

  # Fallback to OpenAI if Groq fails or is unset
  if not ai_response_text and openai_llm:
    try:
      response = openai_llm.invoke(messages_for_llm)
      ai_response_text = response.content
    except Exception as e:
      print(f"\n[OpenAI LLM ERROR] {e}\n")

  if not ai_response_text:
    ai_response_text = (
        "Sorry sir, I couldn't connect to the AI model right now."
    )
  elif not isinstance(ai_response_text, str):
    ai_response_text = str(ai_response_text)

  # Update Mem0 memory bank
  update_memory(
      user_id=user_id, user_msg=latest_query, ai_msg=ai_response_text
  )

  return {"messages": [AIMessage(content=ai_response_text)]}


# ============================================================
# 6. LANGGRAPH ENGINE & SQLITE COMPILATION
# ============================================================

workflow = StateGraph(State)
workflow.add_node("chatbot", chatbot_node)
workflow.add_edge(START, "chatbot")

# Python 3.11 compatible SQLite connection
connection = sqlite3.connect(
    "leo_memory.db",
    check_same_thread=False,
    isolation_level=None,
)

checkpointer = SqliteSaver(connection)
graph_app = workflow.compile(checkpointer=checkpointer)


# ============================================================
# 7. FASTAPI ENDPOINTS
# ============================================================


class ChatRequest(BaseModel):
  message: str
  user_id: str


@app.get("/")
def health():
  return {
      "status": "healthy",
      "groq_ready": bool(groq_llm),
      "openai_ready": bool(openai_llm),
      "mem0_ready": bool(MEM0_API_KEY),
  }


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
  if not req.message.strip():
    raise HTTPException(status_code=400, detail="Message cannot be empty.")
  if not req.user_id.strip():
    raise HTTPException(status_code=400, detail="user_id cannot be empty.")

  try:
    config = {"configurable": {"thread_id": req.user_id}}
    state_input = {
        "messages": [HumanMessage(content=req.message)],
        "user_id": req.user_id,
    }

    result = graph_app.invoke(state_input, config=config)
    last_message = result["messages"][-1]

    return {"response": last_message.content}

  except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 8. CLI RUNNER
# ============================================================


def run_chat():
  print()
  print("=" * 60)
  print("                LEO AI ASSISTANT")
  print("=" * 60)
  print()

  user_id = input("Enter your unique User ID: ").strip()

  if not user_id:
    print("User ID cannot be empty.")
    return

  print(f"\nAI Agent initialized for user '{user_id}'.")
  print("Type 'quit' to exit.\n")

  config = {"configurable": {"thread_id": user_id}}

  while True:
    try:
      user_input = input("You: ").strip()
    except (KeyboardInterrupt, EOFError):
      print("\n\nGoodbye! 👋")
      break

    if user_input.lower() in {"quit", "exit", "bye"}:
      print("\nGoodbye! 👋")
      break

    if not user_input:
      continue

    state_input = {
        "messages": [HumanMessage(content=user_input)],
        "user_id": user_id,
    }

    try:
      result = graph_app.invoke(state_input, config=config)
      last_message = result["messages"][-1]

      if isinstance(last_message, AIMessage):
        print(f"\nLeo: {last_message.content}\n")

    except Exception as e:
      print(f"\n[ERROR] {e}\n")

if __name__ == "__main__":
  import sys

  if len(sys.argv) > 1 and sys.argv[1] == "cli":
    run_chat()
  else:
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("agent:app", host="0.0.0.0", port=port)