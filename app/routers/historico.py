from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Conciliacao
from app.services.tempo import formatar_dt, formatar_competencia
from app.services.configuracao import contexto_cliente

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/historico")
def listar(request: Request, db: Session = Depends(get_db)):
    registros = db.query(Conciliacao).order_by(Conciliacao.data_hora.desc()).all()
    linhas = [{
        "id": c.id, "quando": formatar_dt(c.data_hora),
        "competencia": formatar_competencia(c.competencia),
        "total": c.total_universo, "gerenciadas": c.qt_gerenciadas,
        "falta_lancar": c.qt_falta_lancar, "falta_arquivar": c.qt_falta_arquivar,
    } for c in registros]
    return templates.TemplateResponse(request, "historico.html", {
        "ativo": "historico", "linhas": linhas, **contexto_cliente(db),
    })
