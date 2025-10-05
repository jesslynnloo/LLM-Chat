import pytest


@pytest.mark.asyncio
async def test_create_and_clear_session(client):
    response = await client.post("/session")
    assert response.status_code == 200
    sid = response.json()["session_id"]

    response = await client.get(f"/session/{sid}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == sid
    assert data["messages"] == []


@pytest.mark.asyncio
async def test_clear_session(client):
    response = await client.post("/session")
    sid = response.json()["session_id"]

    response = await client.delete(f"/session/{sid}")
    assert response.status_code == 200
    assert response.json()["status"] == "cleared"
