"""Guarda de Host/Origin: o app é local e sem login, então qualquer página
aberta no navegador do operador alcança o 127.0.0.1 (CSRF e DNS rebinding)."""


def test_host_estranho_e_barrado(client):
    resp = client.get("/health", headers={"Host": "evil.example"})
    assert resp.status_code == 403
    assert "Host" in resp.text


def test_host_local_com_porta_passa(client):
    assert client.get("/health", headers={"Host": "127.0.0.1:8000"}).status_code == 200
    assert client.get("/health", headers={"Host": "localhost:8000"}).status_code == 200


def test_post_com_origin_externa_e_barrado(client):
    resp = client.post("/aceites/marcar",
                       data={"cnpj": "11222333000199", "numero": "100", "nome": "X",
                             "observacao": "ok", "competencia": "2026-07",
                             "conciliacao_id": "1"},
                       headers={"Origin": "http://evil.example"})
    assert resp.status_code == 403
    assert "Origem" in resp.text


def test_post_sem_origin_passa(client):
    """A janela do app (webview/--app) e o curl não mandam Origin."""
    resp = client.post("/aceites/marcar",
                       data={"cnpj": "11222333000199", "numero": "100", "nome": "X",
                             "observacao": "ok", "competencia": "2026-07",
                             "conciliacao_id": "1"},
                       follow_redirects=False)
    assert resp.status_code == 303


def test_post_com_origin_local_passa(client):
    resp = client.post("/aceites/marcar",
                       data={"cnpj": "11222333000199", "numero": "101", "nome": "X",
                             "observacao": "ok", "competencia": "2026-07",
                             "conciliacao_id": "1"},
                       headers={"Origin": "http://127.0.0.1:8000"},
                       follow_redirects=False)
    assert resp.status_code == 303
