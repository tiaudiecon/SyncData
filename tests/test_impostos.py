from tests.test_conciliar import _sieg_xlsx, _spdata_txt
from tests._fakes import montar_conciliacao


def test_impostos_renderiza(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Detalhamento de Impostos" in r.text
    assert "CSRF" in r.text


def test_impostos_vazio_sem_conciliacao(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Nenhuma conciliação" in r.text
