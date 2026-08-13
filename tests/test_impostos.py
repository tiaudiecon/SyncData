from tests.test_conciliar import _sieg_xlsx, _renew_xlsx, _spdata_txt


def test_impostos_renderiza(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"), "application/octet-stream"),
        "renew": ("renew.xlsx", _renew_xlsx(), "application/octet-stream"),
    }, follow_redirects=False)
    r = client.get("/impostos")           # a mais recente
    assert r.status_code == 200
    assert "Detalhamento de Impostos" in r.text
    assert "CSRF" in r.text


def test_impostos_vazio_sem_conciliacao(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Nenhuma conciliação" in r.text
