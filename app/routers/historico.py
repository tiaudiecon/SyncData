import re
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Conciliacao, ConciliacaoItem
from app.services.tempo import formatar_dt, formatar_competencia, formatar_periodo
from app.services.configuracao import contexto_cliente
from app.routers.resultado import _resumo_itens

router = APIRouter()
templates = Jinja2Templates(directory="templates")

_RX_COMP = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_RX_DATA = re.compile(r"^\d{4}-\d{2}-\d{2}$")   # aaaa-mm-dd (input date)


@router.get("/historico")
def listar(request: Request, ok: str = None, erro: str = None, db: Session = Depends(get_db)):
    registros = db.query(Conciliacao).order_by(Conciliacao.data_hora.desc()).all()
    linhas = []
    for c in registros:
        # Contagens AO VIVO: refletem as tratativas atuais (validada/exceção/aceita).
        # O gerenciamento não regrava as colunas da Conciliação, então ler o valor
        # cru deixava o Histórico defasado em relação ao Resultado.
        resumo, itens = _resumo_itens(db, c)
        prin = [it for it in itens if it["principal"]]
        linhas.append({
            "id": c.id, "quando": formatar_dt(c.data_hora),
            "competencia": formatar_competencia(c.competencia),
            "competencia_raw": c.competencia or "",
            "periodo": formatar_periodo(c.periodo_inicio, c.periodo_fim),
            "periodo_inicio_raw": c.periodo_inicio or "",
            "periodo_fim_raw": c.periodo_fim or "",
            "total": resumo["total_universo"],
            "gerenciadas": resumo["qt_gerenciadas"],
            "falta_lancar": sum(1 for it in prin if it["status_lancamento"] == "falta"),
            "falta_arquivar": sum(1 for it in prin if it["status_arquivo"] == "falta"),
        })
    return templates.TemplateResponse(request, "historico.html", {
        "ativo": "historico", "linhas": linhas, "ok": ok, "erro": erro,
        **contexto_cliente(db),
    })


@router.post("/historico/{cid}/editar")
def editar(cid: int, competencia: str = Form(""), periodo_inicio: str = Form(""),
           periodo_fim: str = Form(""), db: Session = Depends(get_db)):
    """Corrige competência/período da conciliação (não refaz a conciliação)."""
    c = db.query(Conciliacao).filter(Conciliacao.id == cid).first()
    if not c:
        return RedirectResponse(url="/historico?erro=inexistente", status_code=303)
    competencia = (competencia or "").strip()
    if competencia and not _RX_COMP.match(competencia):
        return RedirectResponse(url="/historico?erro=competencia", status_code=303)
    c.competencia = competencia or c.competencia
    c.periodo_inicio = periodo_inicio if _RX_DATA.match(periodo_inicio or "") else ""
    c.periodo_fim = periodo_fim if _RX_DATA.match(periodo_fim or "") else ""
    db.commit()
    return RedirectResponse(url="/historico?ok=editado", status_code=303)


@router.post("/historico/{cid}/excluir")
def excluir(cid: int, db: Session = Depends(get_db)):
    """Remove a conciliação e todos os seus itens."""
    c = db.query(Conciliacao).filter(Conciliacao.id == cid).first()
    if not c:
        return RedirectResponse(url="/historico?erro=inexistente", status_code=303)
    db.query(ConciliacaoItem).filter(ConciliacaoItem.conciliacao_id == cid).delete()
    db.delete(c)
    db.commit()
    return RedirectResponse(url="/historico?ok=excluido", status_code=303)
