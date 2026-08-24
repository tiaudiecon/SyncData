import json
from app.database import SessionLocal, engine, Base
from app.models import Conciliacao, ConciliacaoItem
from app.routers.resultado import montar_resumo_e_itens
from app.services import aliquotas as al
from app.services.aliquotas import garantir_padrao
from app.services import validacoes as serv


def _conc(db, competencia="2026-07"):
    conc = Conciliacao(cnpj="11", competencia=competencia)
    db.add(conc); db.flush()
    imp = {"sieg": {"ir": 0.0, "csrf": 0.0, "iss": 0.0, "inss": 0.0, "optante_sn": False,
                    "descontos": 0.0, "base_calculo": 1000.0, "total": 0.0, "iss_retido": False},
           "spdata": {"iss": 0, "inss": 0, "ir": 0, "csrf": 0, "total": 0}}
    db.add(ConciliacaoItem(
        conciliacao_id=conc.id, numero="55", cnpj_fornecedor="11222333000199",
        nome_fornecedor="FORN X", data_emissao="03/07/2026", valor_bruto=1000.0,
        valor_liquido=1000.0, imp_sieg=0.0, impostos_json=json.dumps(imp),
        status_lancamento="ok", status_arquivo="ok", veredito="gerenciada",
        cancelada=False, sp_valor_bruto=1000.0, sp_valor_liquido=1000.0))
    db.commit(); db.refresh(conc)
    return conc


def test_validada_vai_para_gerenciadas_e_sai_de_erros(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db)
    conc = _conc(db)
    # base 1000: IRPJ esperado 15 (>10), apurado 0 -> divergência (erro), não gerenciada
    _, itens = montar_resumo_e_itens(conc, al.listar(db))
    it = itens[0]
    assert it["pendencia_sieg"] and it["tem_erro"] and not it["eh_gerenciada"]
    # marca como validada nesta competência
    serv.salvar(db, "2026-07", "11.222.333/0001-99", "55", "FORN X", "conferido, sem imposto")
    _, itens2 = montar_resumo_e_itens(conc, al.listar(db), None, serv.mapa(db, "2026-07"))
    it2 = itens2[0]
    assert it2["validada"] and it2["validada_obs"] == "conferido, sem imposto"
    assert it2["eh_gerenciada"] and not it2["tem_erro"] and not it2["pendencia_sieg"]
    db.close()


def test_validada_vale_so_para_a_competencia(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    serv.salvar(db, "2026-07", "11222333000199", "55", "X", "ok")
    assert serv.mapa(db, "2026-07").get(("11222333000199", "55")) == "ok"
    assert serv.mapa(db, "2026-08") == {}          # não vale p/ outra competência
    assert serv.remover(db, "2026-07", "11222333000199", "55") is True
    assert serv.mapa(db, "2026-07") == {}
    db.close()
