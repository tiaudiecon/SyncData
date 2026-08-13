from tests.test_conciliar import _sieg_xlsx, _spdata_txt
from tests._fakes import montar_conciliacao
from app.database import SessionLocal
from app.models import Conciliacao, ConciliacaoItem


def test_processar_pasta_salva_conciliacao(client):
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    assert st["fase"] == "pronto"
    assert st["conciliacao_id"]
    db = SessionLocal()
    conc = db.get(Conciliacao, st["conciliacao_id"])
    it = db.query(ConciliacaoItem).filter_by(conciliacao_id=conc.id).first()
    db.close()
    assert conc.pasta_pdfs
    assert it.arquivo_pdf == "E_100.pdf"
    assert it.veredito == "gerenciada"


def test_processar_pasta_marca_erro_quando_runner_falha(client):
    from app.services.jobs import criar_job, estado
    from app.services.renew_runner import processar_pasta

    def runner_ruim(pasta, on_progress=None):
        raise RuntimeError("boom")

    jid = criar_job()
    processar_pasta(jid, "qualquer", [], [], [], "04541288000162", runner=runner_ruim)
    assert estado(jid)["fase"] == "erro"
    assert "boom" in estado(jid)["erro"]
