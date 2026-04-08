def test_api_key_required_when_set(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    from app.core.config import get_settings
    from app.db.session import reset_engine_for_tests
    from fastapi.testclient import TestClient

    from app.main import create_app

    get_settings.cache_clear()
    reset_engine_for_tests()
    client = TestClient(create_app())
    r = client.post("/chat", json={"message": "hello search"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid or missing API key"

def test_api_key_x_api_key_header(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    from app.core.config import get_settings
    from app.db.session import reset_engine_for_tests
    from fastapi.testclient import TestClient

    from app.main import create_app

    get_settings.cache_clear()
    reset_engine_for_tests()
    client = TestClient(create_app())
    r = client.post(
        "/chat",
        json={"message": "hello search"},
        headers={"X-API-Key": "secret"},
    )
    assert r.status_code == 200
