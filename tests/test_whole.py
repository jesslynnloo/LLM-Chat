import requests

BASE_URL = "http://localhost:8000"


def test_end_to_end_health():
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_end_to_end_session_and_chat():
    response = requests.post(f"{BASE_URL}/session")
    sid = response.json()["session_id"]

    response = requests.post(f"{BASE_URL}/chat", json={
        "session_id": sid, "user_message": "Hello"
    })
    assert response.status_code == 200
