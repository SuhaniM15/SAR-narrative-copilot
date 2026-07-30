def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_and_me(client, analyst_token):
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {analyst_token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "analyst@example.com"
    assert me.json()["role"] == "analyst"
