import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def test_client():
    """Create a shared TestClient for all API tests."""
    with TestClient(app) as client:
        yield client
