import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Função utilitária para obter token real de admin
@pytest.fixture(scope="session")
def admin_token():
    resp = client.post("/auth/login", json={"username": "Admin", "password": "#agenciatitan2026"})
    assert resp.status_code == 200
    return resp.json()["access_token"]

# Função utilitária para obter token real de usuário comum (ajuste conforme necessário)
@pytest.fixture(scope="session")
def user_token():
    resp = client.post("/auth/login", json={"username": "native", "password": "Native2026"})
    if resp.status_code == 200:
        return resp.json()["access_token"]
    return None

def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.parametrize("endpoint,params,role,expected_status", [
    # /metrics/summary
    ("/metrics/summary", {"period": "daily"}, "admin", 200),
    ("/metrics/summary", {"period": "weekly"}, "admin", 200),
    ("/metrics/summary", {"period": "monthly"}, "admin", 200),
    ("/metrics/summary", {"period": "daily"}, "user", 200),
    ("/metrics/summary", {"period": "weekly"}, "user", 200),
    ("/metrics/summary", {"period": "monthly"}, "user", 200),
    # /metrics/by-squad (apenas admin)
    ("/metrics/by-squad", {"period": "daily"}, "admin", 200),
    ("/metrics/by-squad", {"period": "daily"}, "user", 403),
    # /metrics/hourly/period
    ("/metrics/hourly/period", {"period": "weekly"}, "admin", 200),
    ("/metrics/hourly/period", {"period": "weekly"}, "user", 200),
    # /metrics/by-checkout
    ("/metrics/by-checkout", {"period": "monthly"}, "admin", 200),
    ("/metrics/by-checkout", {"period": "monthly"}, "user", 200),
    # /metrics/by-product
    ("/metrics/by-product", {"period": "monthly"}, "admin", 200),
    ("/metrics/by-product", {"period": "monthly"}, "user", 200),
    # /metrics/conversion-breakdown
    ("/metrics/conversion-breakdown", {"period": "monthly"}, "admin", 200),
    ("/metrics/conversion-breakdown", {"period": "monthly"}, "user", 200),
])
def test_metrics_endpoints(endpoint, params, role, expected_status, admin_token, user_token):
    token = admin_token if role == "admin" else user_token
    assert token is not None, "Token de usuário não configurado."
    response = client.get(endpoint, params=params, headers=auth_headers(token))
    assert response.status_code == expected_status
