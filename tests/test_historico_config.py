def test_historico_vazio(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.get("/historico")
    assert resp.status_code == 200
    assert "Nenhuma conciliação ainda." in resp.text


def test_configuracoes_altera_cnpj(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/configuracoes",
                       data={"cnpj": "11.222.333/0001-44", "razao_social": "NOVO"},
                       follow_redirects=False)
    assert resp.status_code == 303
    pagina = client.get("/configuracoes")
    assert "11222333000144" in pagina.text
