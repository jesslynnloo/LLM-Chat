import os
import asyncio
import sys
import uuid
from typing import List, Dict
import logging

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, MessagesPlaceholder, HumanMessagePromptTemplate
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import uvicorn
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import MetaData, Table, Column, String, DateTime, text, select, insert, delete

load_dotenv()

logger = logging.getLogger("uvicorn.error")

MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")
DB_URL = os.getenv("DB_URL")
async_engine = create_async_engine(DB_URL)

SYSTEM_PROMPT = "You are a helpful assistant that answers questions from the user."

PROMPT = ChatPromptTemplate.from_messages(
    [
        SystemMessagePromptTemplate.from_template("{system_prompt}"),
        MessagesPlaceholder(variable_name="history"),
        HumanMessagePromptTemplate.from_template("{input}"),
    ]
)

metadata = MetaData()
chat_sessions = Table(
    "chat_sessions",
    metadata,
    Column("session_id", String, primary_key=True),
    Column("created_at", DateTime, server_default=text("(DATETIME('now'))")),
)


class ChatIn(BaseModel):
    session_id: str = "1"
    user_message: str


class HistoryOut(BaseModel):
    session_id: str
    messages: List[Dict[str, str]]


def build_chain():
    llm = ChatOpenAI(model=MODEL, temperature=0.7, streaming=True)
    return PROMPT | llm


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    await async_engine.dispose()


app = FastAPI(title="LLM Chat", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:7860",
        "http://127.0.0.1:7860",
        "http://ui:7860"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/session")
async def create_new_session():
    new_session_id = str(uuid.uuid4())
    async with async_engine.begin() as conn:
        await conn.execute(insert(chat_sessions).values(session_id=new_session_id))
    return {"session_id": new_session_id}


@app.get("/sessions")
async def list_all_sessions():
    async with async_engine.connect() as conn:
        session_list = (await conn.execute(select(chat_sessions.c.session_id))).scalars().all()
    return {"sessions": session_list}


@app.get("/session/{session_id}/history", response_model=HistoryOut)
async def get_history(session_id):
    history = SQLChatMessageHistory(session_id=session_id, connection=async_engine)

    messages_raw = await history.aget_messages()
    msgs = []
    for m in messages_raw:
        if isinstance(m, AIMessage):
            role = "assistant"
        elif isinstance(m, HumanMessage):
            role = "user"
        elif isinstance(m, SystemMessage):
            role = "system"
        else:
            role = "unknown"
        msgs.append({"role": role, "content": m.content})

    return HistoryOut(session_id=session_id, messages=msgs)


@app.post("/chat")
async def chat(body: ChatIn):
    sid = body.session_id.strip()
    user_msg = body.user_message.strip()

    if not user_msg:
        raise HTTPException(status_code=400, detail="user_message cannot be empty.")

    chain = build_chain()
    inputs = {
        "system_prompt": SYSTEM_PROMPT,
        "input": user_msg,
    }

    config = {
        "configurable": {"session_id": sid}
    }

    chain_with_history = RunnableWithMessageHistory(
        chain,
        lambda session_id: SQLChatMessageHistory(
            session_id=session_id, connection=async_engine,
        ),
        input_messages_key="input",
        history_messages_key="history",
    )

    async def gen():
        try:
            stream = chain_with_history.astream(inputs, config=config)
            async for chunk in stream:
                s = chunk if isinstance(chunk, str) else getattr(chunk, "content", "")
                if not s:
                    continue
                yield s
        except Exception as e:
            logger.exception("Streaming failed: %s", e)
            yield f"\n\n[ERROR] Provider failed: {type(e).__name__}: {e}"

    return StreamingResponse(gen(), media_type="text/plain")


@app.delete("/session/{session_id}")
async def clear_session_history(session_id: str):
    history = SQLChatMessageHistory(session_id=session_id, connection=async_engine)
    await history.aclear()
    async with async_engine.begin() as conn:
        await conn.execute(delete(chat_sessions).where(chat_sessions.c.session_id == session_id))
    return {"status": "cleared", "session_id": session_id}


if __name__ == "__main__":
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(app, host="0.0.0.0", port=8000)
