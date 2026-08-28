from app.database import SessionLocal, engine, Base
from app.models import Conciliacao, ConciliacaoItem
from app.services import vinculos as serv


def test_service_mapa_salvar_remover():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 970.0, "num errado no spdata")
    m = serv.mapa(db, "2026-07")
    v = m[("54017315000170", "300")]
    assert v["sp_numero"] == "0" and v["sp_valor"] == 970.0 and "errado" in v["obs"]
    assert serv.mapa(db, "2026-08") == {}                 # isolado por competência
    assert serv.remover(db, "2026-07", "54017315000170", "300") is True
    assert serv.mapa(db, "2026-07") == {}
    db.close()


from app.routers.resultado import montar_resumo_e_itens
from app.services import aliquotas as serv_al


def _conc_nota_e_orfao(db, competencia="2026-07"):
    """Conciliação com: NOTA Sieg 300 'faltou lançar' + lançamento SP 'sem sieg'
    (mesmo CNPJ e valor, número 0)."""
    conc = Conciliacao(cnpj="11", competencia=competencia,
                       periodo_inicio="2026-07-01", periodo_fim="2026-07-31")
    db.add(conc); db.flush()
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="300",
        cnpj_fornecedor="54017315000170", nome_fornecedor="FORN", data_emissao="03/07/2026",
        valor_bruto=970.0, valor_liquido=970.0, imp_sieg=0.0,
        status_lancamento="falta", status_arquivo="ok", veredito="pendente", cancelada=False))
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="0",
        cnpj_fornecedor="54017315000170", nome_fornecedor="FORN", data_emissao="",
        valor_bruto=0.0, valor_liquido=0.0, sp_valor_bruto=970.0, sp_valor_liquido=970.0,
        imp_spdata=0.0, status_lancamento="", status_arquivo="", veredito="sp_sem_sieg",
        cancelada=False))
    db.commit(); db.refresh(conc); return conc


def test_vinculo_valores_batem_vira_gerenciada_e_tira_orfao(client):  # client garante schema
    db = SessionLocal(); serv_al.garantir_padrao(db)
    conc = _conc_nota_e_orfao(db)
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 970.0, "num errado")
    resumo, itens = montar_resumo_e_itens(conc, serv_al.listar(db), None, None, None,
                                          serv.mapa(db, "2026-07"))
    nota = next(i for i in itens if i["numero"] == "300")
    assert nota["vinculada"] and nota["eh_gerenciada"] and not nota["tem_erro"]
    assert resumo["qt_vinculadas"] == 1
    assert resumo["qt_sp_sem_sieg"] == 0            # o órfão foi consumido
    db.close()


def test_vinculo_valores_divergem_vira_ressalva(client):
    db = SessionLocal(); serv_al.garantir_padrao(db)
    conc = _conc_nota_e_orfao(db)
    # órfão com valor diferente da nota (970) -> divergência
    orf = db.query(ConciliacaoItem).filter(ConciliacaoItem.veredito == "sp_sem_sieg").first()
    orf.sp_valor_bruto = 900.0; orf.sp_valor_liquido = 900.0; db.commit()
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 900.0, "num errado, valor diverge")
    resumo, itens = montar_resumo_e_itens(conc, serv_al.listar(db), None, None, None,
                                          serv.mapa(db, "2026-07"))
    nota = next(i for i in itens if i["numero"] == "300")
    assert nota["vinculada"] and nota["tem_erro"]          # Ressalva (diverge)
    assert nota["status_lancamento"] == "diverg"
    db.close()
