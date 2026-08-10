from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine
from app import models


def test_app_sobe_e_cria_tabelas():
    Base.metadata.create_all(bind=engine)
    nomes = set(Base.metadata.tables.keys())
    assert {"config", "conciliacao", "conciliacao_item"} <= nomes


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
