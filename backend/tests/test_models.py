def test_provider_requires_base_url(client, auth):
    r = client.post("/api/models", json={"name": "x", "kind": "openai_compatible", "base_url": ""}, headers=auth)
    assert r.status_code == 400

def test_ollama_provider_unreachable_gives_useful_error(client, auth):
    r = client.post("/api/models", json={"name": "local ollama", "kind": "ollama",
                                          "base_url": "http://127.0.0.1:59999/v1"}, headers=auth)
    assert r.status_code == 200
    pid = r.json()["id"]
    r = client.post(f"/api/models/{pid}/test", headers=auth).json()
    assert r["ok"] is False and "connection failed" in r["error"]

def test_api_key_never_returned(client, auth):
    r = client.post("/api/models", json={"name": "k", "kind": "openai_compatible",
                                          "base_url": "http://example.invalid/v1", "api_key": "sk-secret-123"}, headers=auth)
    pid = r.json()["id"]
    body = client.get("/api/models", headers=auth).json()
    assert all("sk-secret-123" not in str(p) for p in body)
    assert any(p["has_api_key"] for p in body)
