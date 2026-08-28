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
