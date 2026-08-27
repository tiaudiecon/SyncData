import json
from app.database import SessionLocal, engine, Base
from app.models import Conciliacao, ConciliacaoItem
from app.routers.resultado import montar_resumo_e_itens
from app.services import aliquotas as al
from app.services.aliquotas import garantir_padrao
from app.services import aceites as serv
from app.services.pacote_dados import gerar_pacote_dados


def _item_kwargs(veredito="ressalva", optante_sn=True, ir=0.0, base=1000.0):
    """Item RESSALVA (lançamento diverge). SN + impostos 0 => sem pendência de
    imposto (isola a divergência de valor/arquivo)."""
    imp = {"sieg": {"ir": ir, "csrf": 0.0, "iss": 0.0, "inss": 0.0, "optante_sn": optante_sn,
                    "descontos": 0.0, "base_calculo": base, "total": ir, "iss_retido": False},
           "spdata": {"iss": 0, "inss": 0, "ir": ir, "csrf": 0, "total": ir}}
    return dict(numero="55", cnpj_fornecedor="11222333000199", nome_fornecedor="FORN X",
                data_emissao="03/07/2026", valor_bruto=base, valor_liquido=base,
                imp_sieg=ir, impostos_json=json.dumps(imp),
                status_lancamento="diverg", status_arquivo="ok", veredito=veredito,
                cancelada=False, sp_valor_bruto=base, sp_valor_liquido=base - 1)


def _conc(db, competencia="2026-07", **kw):
    conc = Conciliacao(cnpj="11", competencia=competencia)
    db.add(conc); db.flush()
    db.add(ConciliacaoItem(conciliacao_id=conc.id, **_item_kwargs(**kw)))
    db.commit(); db.refresh(conc)
    return conc


def test_service_mapa_salvar_remover(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    serv.salvar(db, "2026-07", "11.222.333/0001-99", "55", "X", "valor confere na origem")
    assert serv.mapa(db, "2026-07").get(("11222333000199", "55")) == "valor confere na origem"
    assert serv.mapa(db, "2026-08") == {}                 # não vale p/ outra competência
    assert serv.remover(db, "2026-07", "11222333000199", "55") is True
    assert serv.mapa(db, "2026-07") == {}
    db.close()


def test_aceite_ressalva_vira_gerenciada(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db)
    conc = _conc(db)
    _, itens = montar_resumo_e_itens(conc, al.listar(db))
    it = itens[0]
    assert it["veredito"] == "ressalva" and it["tem_erro"] and not it["eh_gerenciada"]
    assert not it["pendencia_sieg"]                        # imposto ok (SN) — só a divergência de valor
    serv.salvar(db, "2026-07", "11222333000199", "55", "FORN X", "valor correto na origem")
    resumo, itens2 = montar_resumo_e_itens(conc, al.listar(db), None, None, serv.mapa(db, "2026-07"))
    it2 = itens2[0]
    assert it2["aceita"] and it2["aceita_obs"] == "valor correto na origem"
    assert it2["eh_gerenciada"] and not it2["tem_erro"]
    assert resumo["qt_aceitas"] == 1 and resumo["qt_erros"] == 0 and resumo["qt_gerenciadas"] == 1
    db.close()


def test_aceite_desfazer_volta_a_erro(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db)
    conc = _conc(db)
    serv.salvar(db, "2026-07", "11222333000199", "55", "FORN X", "ok")
    serv.remover(db, "2026-07", "11222333000199", "55")
    _, itens = montar_resumo_e_itens(conc, al.listar(db), None, None, serv.mapa(db, "2026-07"))
    assert itens[0]["tem_erro"] and not itens[0]["aceita"] and not itens[0]["eh_gerenciada"]
    db.close()


def test_aceite_ortogonal_ao_imposto(client):
    # ressalva NÃO-SN, imposto divergente: aceitar limpa valor/arquivo mas o imposto continua erro
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db)
    conc = _conc(db, optante_sn=False, ir=0.0)            # base 1000 -> IRPJ esperado 15 > 0 -> pendência
    serv.salvar(db, "2026-07", "11222333000199", "55", "FORN X", "valor ok")
    _, itens = montar_resumo_e_itens(conc, al.listar(db), None, None, serv.mapa(db, "2026-07"))
    it = itens[0]
    assert it["aceita"] and it["pendencia_sieg"]          # imposto ainda em aberto
    assert it["tem_erro"] and not it["eh_gerenciada"]     # continua erro por causa do imposto
    db.close()


def test_export_carrega_aceita(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db)
    conc = _conc(db)
    serv.salvar(db, "2026-07", "11222333000199", "55", "FORN X", "ok origem")
    resumo, itens = montar_resumo_e_itens(conc, al.listar(db), None, None, serv.mapa(db, "2026-07"))
    pacote = gerar_pacote_dados(resumo, itens, conc)
    assert pacote["resumo"]["aceitas"] == 1
    assert pacote["itens"][0]["aceita"] == {"observacao": "ok origem"}
    db.close()


def test_rota_marcar_e_desfazer(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db); conc = _conc(db); cid = conc.id; db.close()
    r = client.post("/aceites/marcar", data={
        "cnpj": "11222333000199", "numero": "55", "nome": "FORN X",
        "observacao": "valor correto", "competencia": "2026-07", "conciliacao_id": cid},
        follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/resultado/{cid}"
    assert serv.mapa(SessionLocal(), "2026-07").get(("11222333000199", "55")) == "valor correto"
    r2 = client.post("/aceites/desfazer", data={
        "cnpj": "11222333000199", "numero": "55",
        "competencia": "2026-07", "conciliacao_id": cid}, follow_redirects=False)
    assert r2.status_code == 303
    assert serv.mapa(SessionLocal(), "2026-07") == {}
