import os
import sys
import importlib
import pytest
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager


# Manually append project root to sys.path so that can import
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)


@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    # use a dedicated db file just for testing
    tmp_db = os.path.abspath("tests/test_chat.db")
    os.environ["DB_URL"] = f"sqlite+aiosqlite:///{tmp_db}"
    os.environ.setdefault("OPENAI_MODEL", "gpt-4o-mini")

    yield

@pytest.fixture
async def client(set_test_env):
    import app
    importlib.reload(app)

    # create tables
    if hasattr(app, "metadata"):
        async with app.async_engine.begin() as conn:
            await conn.run_sync(app.metadata.create_all)

    async with LifespanManager(app.app):
        transport = ASGITransport(app=app.app)
        async with AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client
