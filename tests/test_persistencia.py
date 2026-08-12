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
                         1000.0, 900.0, irpj=100.0)
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
