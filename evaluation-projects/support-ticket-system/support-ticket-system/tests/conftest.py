import pytest
from fastapi.testclient import TestClient

from app.classifier import Classification
from app.config import Settings
from app.main import create_app
from app.models import Category, Priority


class FakeClassifier:
    """Deterministic stand-in for GPT; records how often it was called."""
    name = "fake"

    def __init__(self):
        self.calls = 0

    def classify(self, title, description):
        self.calls += 1
        return Classification(Category.technical_issue, Priority.high, "Customer is blocked.", "ai")


class ExplodingClassifier:
    name = "boom"

    def classify(self, title, description):
        raise RuntimeError("LLM exploded")


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "tickets.db")


@pytest.fixture
def fake():
    return FakeClassifier()


@pytest.fixture
def client(db_path, fake):
    settings = Settings(database_path=db_path)
    return TestClient(create_app(settings, fake))


GOOD = {"title": "Cannot log in", "description": "I get an error when I try to sign in."}
