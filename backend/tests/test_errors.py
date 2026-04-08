def test_validation_error_json_shape(client):
    r = client.post("/chat", json={"message": ""})
    assert r.status_code == 422
    body = r.json()
    assert body.get("code") == "validation_error"
    assert isinstance(body.get("detail"), list)
