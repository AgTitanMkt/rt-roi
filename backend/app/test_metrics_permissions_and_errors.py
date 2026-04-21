import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture(scope="session")
def admin_token():
    resp = client.post("/auth/login", json={"username": "Admin", "password": "#agenciatitan2026"})
    assert resp.status_code == 200
    return resp.json()["access_token"]

@pytest.fixture(scope="session")
def user_token():
    resp = client.post("/auth/login", json={"username": "native", "password": "Native2026"})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None

# Testes de permissão e resposta para /metrics/by-squad
def test_by_squad_admin(admin_token):
    response = client.get("/metrics/by-squad", params={"period": "daily"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200

def test_by_squad_user_forbidden(user_token):
    if user_token is None:
        pytest.skip("Usuário comum não configurado para login de teste.")
    response = client.get("/metrics/by-squad", params={"period": "daily"}, headers={"Authorization": f"Bearer {user_token}"})
    assert response.status_code == 403

# Testes de parâmetros inválidos
def test_summary_invalid_period(admin_token):
    response = client.get("/metrics/summary", params={"period": "invalid"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code in (422, 400)

def test_hourly_period_missing_dates(admin_token):
    # date_start sem date_end
    response = client.get("/metrics/hourly/period", params={"period": "weekly", "date_start": "2026-04-01"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 422
    # date_end sem date_start
    response = client.get("/metrics/hourly/period", params={"period": "weekly", "date_end": "2026-04-07"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 422
