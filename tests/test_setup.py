def test_setup_salva_cnpj(client):
    resp = client.post("/setup", data={"cnpj": "04.541.288/0001-62",
                                        "razao_social": "HOSPITAL SAO SEBASTIAO"},
                        follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
