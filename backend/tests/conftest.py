import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def test_client():
    """Tạo một TestClient dùng chung cho tất cả các bài test API."""
    with TestClient(app) as client:
        yield client
