import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user, get_optional_user


# Mock authenticated user fixture
MOCK_USER = {
    "uid": "test_mock_user_uid_12345",
    "email": "test_user@certverify.com",
    "email_verified": True,
    "name": "Test User",
    "picture": None,
    "auth_time": 1724836000,
    "claims": {"uid": "test_mock_user_uid_12345", "email": "test_user@certverify.com"}
}


@pytest.fixture
def mock_user():
    return MOCK_USER


@pytest.fixture
def client():
    """Provides a standard unauthenticated TestClient."""
    return TestClient(app)


@pytest.fixture
def auth_client():
    """Provides an authenticated TestClient with Firebase get_current_user overridden."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[get_optional_user] = lambda: MOCK_USER
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_certificate_image():
    """Creates a sample dummy JPEG certificate image in memory."""
    img = Image.new("RGB", (800, 600), color=(245, 240, 220))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    buffer.seek(0)
    return buffer.getvalue()
