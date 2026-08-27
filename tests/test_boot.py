import socket
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
    dados = resp.json()
    assert dados["ok"] is True and "token" in dados


def test_health_devolve_o_token_do_boot(monkeypatch):
    """O lançador usa o token p/ saber que quem respondeu na porta é ESTE
    servidor (e não outro processo que já estivesse escutando ali)."""
    monkeypatch.setenv("SYNCDATA_BOOT_TOKEN", "abc123token")
    resp = TestClient(app).get("/health")
    assert resp.json() == {"ok": True, "token": "abc123token"}


def test_porta_livre_desvia_de_porta_ocupada():
    """Porta configurada ocupada por outro processo -> escolhe uma livre."""
    import run
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ocupado:
        ocupado.bind(("127.0.0.1", 0))
        ocupado.listen(1)
        porta_ocupada = ocupado.getsockname()[1]
        escolhida = run.porta_livre("127.0.0.1", porta_ocupada)
        assert escolhida != porta_ocupada and escolhida > 0
    # com a porta livre, devolve a própria porta pedida
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        livre = s.getsockname()[1]
    assert run.porta_livre("127.0.0.1", livre) == livre
