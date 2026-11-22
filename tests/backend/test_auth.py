from tests.backend.conftest import PASSWORD


def test_protected_endpoints_require_session(client):
    for path in ("/api/dashboard", "/api/alerts", "/api/neurodata/records", "/api/neurodata/layers"):
        assert client.get(path).status_code == 401, path


def test_bad_credentials(client):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "incorrecta"})
    assert r.status_code == 401


def test_me_and_logout(client):
    r = client.post("/api/auth/login", json={"username": "lector", "password": PASSWORD})
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=h).json()["role_key"] == "lector"
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_roles_enforced(client, reader_h, analyst_h):
    alert = {"title": "Prueba", "level": "bajo", "source_name": "test", "uncertainty": "alta",
             "is_simulated": True}
    assert client.post("/api/alerts", json=alert, headers=reader_h).status_code == 403
    assert client.get("/api/auth/users", headers=analyst_h).status_code == 403


def test_admin_creates_user_with_strong_password(client, admin_h):
    weak = {"username": "debil", "password": "1234567890", "role_key": "lector"}
    assert client.post("/api/auth/users", json=weak, headers=admin_h).status_code == 422
    ok = {"username": "nuevo", "password": "Fuerte-clave-99", "role_key": "lector"}
    assert client.post("/api/auth/users", json=ok, headers=admin_h).status_code == 201
    assert client.post("/api/auth/users", json=ok, headers=admin_h).status_code == 409


def test_bruteforce_lockout(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"username": "bloqueo", "password": "x"})
    r = client.post("/api/auth/login", json={"username": "bloqueo", "password": "x"})
    assert r.status_code == 429


def test_failed_login_never_stores_typed_text(client, admin_h):
    secreto = "MiClaveSecreta-escrita-en-usuario"
    client.post("/api/auth/login", json={"username": secreto, "password": "x"})
    ops = client.get("/api/neurocore/operations?limit=200", headers=admin_h).json()
    assert secreto.lower() not in str(ops).lower()


def test_reports_endpoint(client, analyst_h):
    assert client.get("/api/reports", headers=analyst_h).status_code == 200
    assert client.get("/api/reports").status_code == 401


def test_operations_are_audited(client, admin_h):
    ops = client.get("/api/neurocore/operations", headers=admin_h).json()
    actions = {o["action"] for o in ops}
    assert "login" in actions
    assert all("password" not in str(o["details"]).lower() for o in ops)
