import asyncio
import pytest
from langchain_core.messages import HumanMessage, AIMessage

# Basic mock that simulates a streaming LLM chain
class FakeStreamChain:
    def with_config(self, *a, **k): return self
    def bind(self, *a, **k): return self
    def with_listeners(self, *a, **k): return self
    async def with_alisteners(self, *a, **k): return self

    async def astream(self, inputs, config=None):
        text = inputs["input"]
        for chunk in ["HEL", "LO: ", text]:
            await asyncio.sleep(0)
            yield chunk

# Fake SQL history
class FakeSQLChatMessageHistory:
    _STORE = {}

    def __init__(self, session_id=None, connection=None):
        self._sid = session_id or "default"
        FakeSQLChatMessageHistory._STORE.setdefault(self._sid, [])

    async def aget_messages(self):
        return list(FakeSQLChatMessageHistory._STORE.get(self._sid, []))

    async def aadd_message(self, message):
        FakeSQLChatMessageHistory._STORE[self._sid].append(message)

    async def aclear(self):
        FakeSQLChatMessageHistory._STORE[self._sid].clear()

# Mock how RunnableWithMessageHistory works (simplified)
class FakeHistoryWrapper:
    def __init__(self, underlying, history_factory, **kwargs):
        self._u = underlying
        self._history_factory = history_factory

    def with_config(self, *a, **k): return self
    def bind(self, *a, **k): return self
    def with_listeners(self, *a, **k): return self
    async def with_alisteners(self, *a, **k): return self

    async def astream(self, inputs, config=None):
        cfg = config or {}
        sid = cfg.get("configurable", {}).get("session_id", "default")
        history = self._history_factory(sid)

        # Store user message
        if "input" in inputs:
            await history.aadd_message(HumanMessage(content=inputs["input"]))

        full_response = ""
        async for chunk in self._u.astream(inputs, config=config):
            full_response += chunk
            yield chunk

        # Save the assistant reply after streaming
        await history.aadd_message(AIMessage(content=full_response))

@pytest.mark.asyncio
async def test_chat(client, monkeypatch):
    import app as backend

    monkeypatch.setattr(backend, "build_chain", lambda: FakeStreamChain())
    monkeypatch.setattr(backend, "SQLChatMessageHistory", FakeSQLChatMessageHistory)
    monkeypatch.setattr(
        backend,
        "RunnableWithMessageHistory",
        lambda chain, history_factory, **kw: FakeHistoryWrapper(chain, history_factory, **kw),
    )

    # Create a session first
    response = await client.post("/session")
    assert response.status_code == 200
    session_id = response.json()["session_id"]

    # Test chat
    payload = {"session_id": session_id, "user_message": "test message"}
    async with client.stream("POST", "/chat", json=payload) as resp:
        assert resp.status_code == 200
        full_response = ""
        async for chunk in resp.aiter_bytes():
            full_response += chunk.decode("utf-8", errors="ignore")

    assert "HEL" in full_response and "LO: " in full_response and "test message" in full_response

    # Test if history is written correctly
    r = await client.get(f"/session/{session_id}/history")
    assert r.status_code == 200
    roles = [m["role"] for m in r.json()["messages"]]
    assert "user" in roles and "assistant" in roles
