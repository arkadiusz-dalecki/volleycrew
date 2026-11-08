from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_liveness_survives_unavailable_database():
    app = create_app(Settings(database_url="postgresql+asyncpg://unused@127.0.0.1:1/unavailable"))
    with TestClient(app) as client:
        assert client.get("/api/v1/health/live").json() == {"status": "ok"}
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json()["code"] == "not_ready"
        assert "unused" not in response.text
        assert "unavailable" not in response.text


def test_not_found_uses_api_error_contract():
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/missing")
        assert response.status_code == 404
        assert response.json() == {"code": "not_found", "message": "Nie można wykonać żądania."}


def test_unexpected_exception_does_not_expose_details():
    app = create_app()

    @app.get("/test-failure")
    async def fail():
        raise RuntimeError("secret-connection-details")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-failure")
        assert response.status_code == 500
        assert response.json()["code"] == "internal_error"
        assert "secret-connection-details" not in response.text


def test_validation_error_does_not_echo_user_input():
    app = create_app()

    @app.get("/test-validation")
    async def validate(value: int):
        return {"value": value}

    with TestClient(app) as client:
        response = client.get("/test-validation", params={"value": "private-input"})
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
        assert "private-input" not in response.text
