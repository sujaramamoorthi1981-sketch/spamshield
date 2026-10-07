def test_auth_required(client):
    assert client.post("/api/detect", json={"text": "hi"}).status_code == 401


def test_detect_history_stats(client, auth_headers):
    spam = client.post("/api/detect", json={"text": "WINNER!! Claim your free prize now http://x.top"}, headers=auth_headers)
    assert spam.status_code == 200 and spam.json()["data"]["label"] == "spam"
    ham = client.post("/api/detect", json={"text": "See you at 6, bring the notes"}, headers=auth_headers)
    assert ham.json()["data"]["label"] == "ham"
    hist = client.get("/api/history", headers=auth_headers).json()["data"]
    assert len(hist) == 2
    assert len(client.get("/api/history?label=spam", headers=auth_headers).json()["data"]) == 1
    s = client.get("/api/stats", headers=auth_headers).json()["data"]
    assert s["total"] == 2 and s["spam"] == 1
    assert client.delete(f"/api/history/{hist[0]['id']}", headers=auth_headers).status_code == 200
    assert client.delete(f"/api/history/{hist[0]['id']}", headers=auth_headers).status_code == 404


def test_validation_and_batch(client, auth_headers):
    assert client.post("/api/detect", json={"text": ""}, headers=auth_headers).status_code == 422
    assert client.post("/api/detect", json={"text": "x" * 5000}, headers=auth_headers).status_code == 422
    r = client.post("/api/detect/batch", json={"messages": ["hello", "FREE prize click here"]}, headers=auth_headers)
    assert len(r.json()["data"]) == 2


def test_history_isolated_between_users(client, auth_headers):
    client.post("/api/detect", json={"text": "hello"}, headers=auth_headers)
    other = client.post("/api/auth/register", json={"name": "B", "email": "b@example.com", "password": "password123"})
    h = {"Authorization": f"Bearer {other.json()['data']['token']}"}
    assert client.get("/api/history", headers=h).json()["data"] == []
