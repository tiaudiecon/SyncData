def test_historico_vazio(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.get("/historico")
    assert resp.status_code == 200
    assert "Nenhuma conciliação ainda." in resp.text


def test_historico_mostra_periodo_conferencia(client):
    # o Histórico traz a coluna Conferência com o período informado na conciliação
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    from app.database import SessionLocal, engine, Base
    from app.models import Conciliacao
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Conciliacao(cnpj="04541288000162", competencia="2026-07",
                       periodo_inicio="2026-07-01", periodo_fim="2026-07-18"))
    db.commit(); db.close()
    html = client.get("/historico").text
    assert "Conferência" in html                     # cabeçalho da coluna
    assert "01/07/2026 a 18/07/2026" in html         # período na linha


def test_configuracoes_altera_cnpj(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/configuracoes",
                       data={"cnpj": "11.222.333/0001-44", "razao_social": "NOVO"},
                       follow_redirects=False)
    assert resp.status_code == 303
    pagina = client.get("/configuracoes")
    assert "11222333000144" in pagina.text
