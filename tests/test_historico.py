import json
from app.database import SessionLocal, engine, Base
from app.models import Conciliacao, ConciliacaoItem
from app.services.aliquotas import garantir_padrao
from app.services import aceites as serv_aceites


def _conc(db, competencia="2026-07"):
    conc = Conciliacao(cnpj="11", competencia=competencia,
                       periodo_inicio="2026-07-01", periodo_fim="2026-07-31")
    db.add(conc); db.flush()
    imp = {"sieg": {"ir": 0.0, "csrf": 0.0, "iss": 0.0, "inss": 0.0, "optante_sn": True,
                    "descontos": 0.0, "base_calculo": 1000.0, "total": 0.0, "iss_retido": False},
           "spdata": {"total": 0}}
    db.add(ConciliacaoItem(
        conciliacao_id=conc.id, numero="55", cnpj_fornecedor="11222333000199",
        nome_fornecedor="FORN X", data_emissao="03/07/2026", valor_bruto=1000.0,
        valor_liquido=1000.0, imp_sieg=0.0, impostos_json=json.dumps(imp),
        status_lancamento="diverg", status_arquivo="ok", veredito="ressalva",
        cancelada=False, sp_valor_bruto=1000.0, sp_valor_liquido=999.0))   # ressalva (valor diverge)
    db.commit(); db.refresh(conc)
    return conc


def test_historico_editar_competencia_periodo(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db); cid = _conc(db).id; db.close()
    r = client.post(f"/historico/{cid}/editar",
                    data={"competencia": "2026-08", "periodo_inicio": "2026-08-01",
                          "periodo_fim": "2026-08-31"}, follow_redirects=False)
    assert r.status_code == 303
    db = SessionLocal(); c = db.get(Conciliacao, cid)
    assert c.competencia == "2026-08" and c.periodo_fim == "2026-08-31"; db.close()


def test_historico_excluir_remove_conc_e_itens(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db); cid = _conc(db).id; db.close()
    r = client.post(f"/historico/{cid}/excluir", follow_redirects=False)
    assert r.status_code == 303
    db = SessionLocal()
    assert db.get(Conciliacao, cid) is None
    assert db.query(ConciliacaoItem).filter(ConciliacaoItem.conciliacao_id == cid).count() == 0
    db.close()


def test_historico_gerenciadas_ao_vivo(client):
    """A nota ressalva é Erro (Gerenciadas 0); após ACEITAR, ela passa a Gerenciada
    e o Histórico tem que refletir — não pode ficar preso no valor gravado."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db); _conc(db); db.close()
    antes = client.get("/historico").text
    serv_aceites.salvar(SessionLocal(), "2026-07", "11222333000199", "55", "FORN X", "ok origem")
    depois = client.get("/historico").text
    assert antes != depois          # o Histórico recalcula ao vivo (não usa a coluna gravada)
