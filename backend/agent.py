from __future__ import annotations

import os
import sqlite3
from typing import Annotated, TypedDict, List, Union

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver

from langchain_groq import ChatGroq
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
)

from mem0 import MemoryClient


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise ValueError(
        "GROQ_API_KEY is missing from your .env file."
    )

if not os.getenv("MEM0_API_KEY"):
    raise ValueError(
        "MEM0_API_KEY is missing from your .env file."
    )


# ============================================================
# INITIALIZE SERVICES & FASTAPI
# ============================================================

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0.7,
)

m_client = MemoryClient()


# ============================================================
# LANGGRAPH STATE
# ============================================================

class State(TypedDict):
    messages: Annotated[
        List[Union[HumanMessage, AIMessage]],
        add_messages
    ]
    user_id: str


# ============================================================
# MEM0 - RETRIEVE RELEVANT MEMORIES
# ============================================================

def get_relevant_memory(
    query: str,
    user_id: str
) -> str:
    try:
        response = m_client.search(
            query,
            filters={
                "user_id": user_id
            }
        )

        if isinstance(response, dict):
            memories = response.get(
                "results",
                []
            )
        else:
            memories = response

        if not memories:
            return "No prior memories for this user."

        memory_text = []

        for memory in memories:
            if not isinstance(memory, dict):
                continue

            text = memory.get(
                "memory",
                ""
            )

            if text:
                memory_text.append(
                    f"- {text}"
                )

        if not memory_text:
            return "No relevant memories found."

        return "\n".join(memory_text)

    except Exception as e:
        print(
            f"\n[Memory retrieval warning] {e}\n"
        )
        return "Memory system temporarily unavailable."


# ============================================================
# MEM0 - SAVE CONVERSATION
# ============================================================

def update_memory(
    user_id: str,
    user_msg: str,
    ai_msg: str
):
    try:
        messages = [
            {
                "role": "user",
                "content": user_msg
            },
            {
                "role": "assistant",
                "content": ai_msg
            }
        ]

        m_client.add(
            messages,
            user_id=user_id
        )

    except Exception as e:
        print(
            f"\n[Memory update warning] {e}\n"
        )


# ============================================================
# CHATBOT NODE
# ============================================================

def chatbot_node(
    state: State
):
    user_id = state["user_id"]
    latest_message = state["messages"][-1]
    latest_query = latest_message.content

    memory_context = get_relevant_memory(
        latest_query,
        user_id
    )

    system_prompt = f"""
You are Leo, a helpful personal AI assistant.
Your job is to assist the user naturally and intelligently.
You have access to long-term memories about the user.
Use memories ONLY when they are relevant to the current conversation.
Do NOT invent memories.
If a memory is uncertain or unrelated, ignore it.
Be conversational, concise, and helpful.

Relevant User Memories:
{memory_context}
"""

    messages_for_llm = [
        SystemMessage(
            content=system_prompt
        )
    ] + list(state["messages"])

    try:
        response = llm.invoke(
            messages_for_llm
        )
        ai_response_text = response.content

        if not isinstance(
            ai_response_text,
            str
        ):
            ai_response_text = str(
                ai_response_text
            )

    except Exception as e:
        print(
            f"\n[LLM ERROR] {e}\n"
        )
        ai_response_text = (
            "Sorry sir, I couldn't connect "
            "to the AI model right now."
        )

    update_memory(
        user_id=user_id,
        user_msg=latest_query,
        ai_msg=ai_response_text
    )

    return {
        "messages": [
            AIMessage(
                content=ai_response_text
            )
        ]
    }


# ============================================================
# BUILD LANGGRAPH & SQLITE CHECKPOINT
# ============================================================

workflow = StateGraph(State)

workflow.add_node(
    "chatbot",
    chatbot_node
)

workflow.add_edge(
    START,
    "chatbot"
)

connection = sqlite3.connect(
    "leo_memory.db",
    check_same_thread=False
)

checkpointer = SqliteSaver(
    connection
)

graph_app = workflow.compile(
    checkpointer=checkpointer
)


# ============================================================
# FASTAPI ENDPOINTS
# ============================================================

class ChatRequest(BaseModel):
    message: str
    user_id: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    try:
        config = {
            "configurable": {
                "thread_id": req.user_id
            }
        }
        state_input = {
            "messages": [
                HumanMessage(content=req.message)
            ],
            "user_id": req.user_id
        }
        
        result = graph_app.invoke(
            state_input,
            config=config
        )
        
        last_message = result["messages"][-1]
        return {"response": last_message.content}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CLI CHAT
# ============================================================

def run_chat():
    print()
    print("=" * 60)
    print("                LEO AI ASSISTANT")
    print("=" * 60)
    print()

    user_id = input(
        "Enter your unique User ID: "
    ).strip()

    if not user_id:
        print(
            "User ID cannot be empty."
        )
        return

    print()
    print(
        f"AI Agent initialized for user '{user_id}'."
    )
    print(
        "Type 'quit' to exit."
    )
    print()

    config = {
        "configurable": {
            "thread_id": user_id
        }
    }

    while True:
        try:
            user_input = input(
                "You: "
            ).strip()
        except (
            KeyboardInterrupt,
            EOFError
        ):
            print(
                "\n\nGoodbye! 👋"
            )
            break

        if user_input.lower() in {
            "quit",
            "exit",
            "bye"
        }:
            print(
                "\nGoodbye! 👋"
            )
            break

        if not user_input:
            continue

        state_input = {
            "messages": [
                HumanMessage(
                    content=user_input
                )
            ],
            "user_id": user_id
        }

        try:
            result = graph_app.invoke(
                state_input,
                config=config
            )

            last_message = (
                result["messages"][-1]
            )

            if isinstance(
                last_message,
                AIMessage
            ):
                print(
                    f"\nLeo: {last_message.content}\n"
                )

        except Exception as e:
            print(
                f"\n[ERROR] {e}\n"
            )


if __name__ == "__main__":
    run_chat()