import os
import tempfile
from app.database import SessionLocal
from app.models import Conciliacao, ConciliacaoItem


def _conc_com_pdf(pasta, arquivo_pdf):
    db = SessionLocal()
    c = Conciliacao(cnpj="04541288000162", pasta_pdfs=pasta)
    db.add(c); db.flush()
    it = ConciliacaoItem(conciliacao_id=c.id, numero="100",
                         arquivo_pdf=arquivo_pdf, status_arquivo="ok")
    db.add(it); db.commit()
    iid = it.id
    db.close()
    return iid


def test_serve_pdf_inline(client):
    pasta = tempfile.mkdtemp(prefix="pdf_")
    with open(os.path.join(pasta, "E_100.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 fake")
    iid = _conc_com_pdf(pasta, "E_100.pdf")
    r = client.get(f"/pdf/{iid}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_bloqueia_path_traversal(client):
    pasta = tempfile.mkdtemp(prefix="pdf_")
    iid = _conc_com_pdf(pasta, "..\\..\\segredo.pdf")
    assert client.get(f"/pdf/{iid}").status_code == 404


def test_pdf_ausente_404(client):
    pasta = tempfile.mkdtemp(prefix="pdf_")
    iid = _conc_com_pdf(pasta, "nao_existe.pdf")
    assert client.get(f"/pdf/{iid}").status_code == 404
