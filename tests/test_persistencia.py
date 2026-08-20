import json
from datetime import date
from app.database import Base, engine, SessionLocal
from app.models import Conciliacao, ConciliacaoItem  # noqa
from app.services.parser_sieg import NotaSieg
from app.services.parser_spdata import LancamentoSpData
from app.services.matcher import conciliar
from app.services.persistencia import salvar_conciliacao


def test_persiste_impostos_e_lado_spdata():
    Base.metadata.create_all(bind=engine)
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3), 1000.0, 900.0,
                 False, ir=100.0, iss=0.0, deducoes=0.0)
    l = LancamentoSpData("100", "100", "11111111000111", "F", date(2026, 7, 3),
                         1000.0, irpj=100.0)              # líq = 1000 − 100 = 900
    from app.services.parser_renew import RegistroRenew
    reg = RegistroRenew("100", "100", "11111111000111", "F", date(2026, 7, 3), 1000.0)
    res = conciliar([n], [], [l], [reg])
    db = SessionLocal()
    conc = salvar_conciliacao(db, "04541288000162",
                              {"spdata": "a", "sieg": "b", "renew": "c"}, res)
    it = db.query(ConciliacaoItem).filter_by(conciliacao_id=conc.id).first()
    assert it.sp_valor_bruto == 1000.0
    assert it.imp_sieg == 100.0 and it.imp_spdata == 100.0
    assert it.tem_desconto is False
    dados = json.loads(it.impostos_json)
    assert dados["sieg"]["ir"] == 100.0
    assert dados["spdata"]["ir"] == 100.0
    db.query(ConciliacaoItem).delete(); db.query(Conciliacao).delete(); db.commit(); db.close()


def test_faltou_lancar_lado_spdata_fica_none():
    Base.metadata.create_all(bind=engine)
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3), 1000.0, 900.0,
                 False, ir=100.0)
    from app.services.parser_renew import RegistroRenew
    reg = RegistroRenew("100", "100", "11111111000111", "F", date(2026, 7, 3), 1000.0)
    res = conciliar([n], [], [], [reg])          # sem SPData -> faltou lançar
    db = SessionLocal()
    conc = salvar_conciliacao(db, "04541288000162",
                              {"spdata": "a", "sieg": "b", "renew": "c"}, res)
    it = db.query(ConciliacaoItem).filter_by(conciliacao_id=conc.id).first()
    assert it.sp_valor_bruto is None and it.sp_valor_liquido is None
    assert it.imp_spdata is None
    assert it.imp_sieg == 100.0                  # lado Sieg segue preenchido
    assert json.loads(it.impostos_json)["spdata"] is None
    db.query(ConciliacaoItem).delete(); db.query(Conciliacao).delete(); db.commit(); db.close()


def test_impostos_json_remap_por_campo():
    Base.metadata.create_all(bind=engine)
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3), 1000.0, 800.0,
                 False, iss=11.0, iss_retido=True, inss=22.0, ir=33.0,
                 pis=1.0, cofins=2.0, csll=3.0, aliquota=5.0, base_calculo=900.0)
    l = LancamentoSpData("100", "100", "11111111000111", "F", date(2026, 7, 3),
                         1000.0, issqn=11.0, inss_pj=20.0, inss_auton=2.0,
                         irpj=30.0, ir_auton=3.0, ir_coop=0.0, csrf=6.0)
    from app.services.parser_renew import RegistroRenew
    reg = RegistroRenew("100", "100", "11111111000111", "F", date(2026, 7, 3), 1000.0)
    res = conciliar([n], [], [l], [reg])
    db = SessionLocal()
    conc = salvar_conciliacao(db, "04541288000162",
                              {"spdata": "a", "sieg": "b", "renew": "c"}, res)
    it = db.query(ConciliacaoItem).filter_by(conciliacao_id=conc.id).first()
    d = json.loads(it.impostos_json)
    assert d["sieg"]["iss"] == 11.0 and d["spdata"]["iss"] == 11.0   # ISSQN -> "iss"
    assert d["sieg"]["inss"] == 22.0 and d["spdata"]["inss"] == 22.0  # 20+2
    assert d["sieg"]["ir"] == 33.0 and d["spdata"]["ir"] == 33.0      # 30+3
    # Sieg CSRF é DERIVADO: total(1000−800=200) − IR(33) − INSS(22) − ISS(11 retido) = 134
    assert d["sieg"]["csrf"] == 134.0
    assert d["spdata"]["csrf"] == 6.0                                 # SPData: campo CSRF direto
    assert d["sieg"]["base_calculo"] == 900.0 and d["sieg"]["aliquota"] == 5.0
    assert d["sieg"]["iss_retido"] is True
    db.query(ConciliacaoItem).delete(); db.query(Conciliacao).delete(); db.commit(); db.close()


def test_persiste_pasta_e_arquivo_pdf(client):
    from app.services.parser_renew import RegistroRenew
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3), 150.0, 150.0, False)
    l = LancamentoSpData("100", "100", "11111111000111", "F", date(2026, 7, 3), 150.0)
    reg = RegistroRenew("100", "100", "11111111000111", "F", date(2026, 7, 3), 150.0,
                        arquivo_pdf="E_100.pdf")
    res = conciliar([n], [], [l], [reg])
    db = SessionLocal()
    conc = salvar_conciliacao(db, "04541288000162",
                              {"spdata": "a", "sieg": "b", "pasta_pdfs": r"C:\pdfs"}, res)
    it = db.query(ConciliacaoItem).filter_by(conciliacao_id=conc.id).first()
    assert conc.pasta_pdfs == r"C:\pdfs"
    assert it.arquivo_pdf == "E_100.pdf"
    db.close()
