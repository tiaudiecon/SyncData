from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.configuracao import obter_config, salvar_config, contexto_cliente

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/configuracoes")
def form(request: Request, db: Session = Depends(get_db)):
    cfg = obter_config(db)
    return templates.TemplateResponse(request, "configuracoes.html", {
        "ativo": "config", "cfg": cfg, **contexto_cliente(db),
    })


@router.post("/configuracoes")
def salvar(cnpj: str = Form(...), razao_social: str = Form(""),
           db: Session = Depends(get_db)):
    salvar_config(db, cnpj, razao_social)
    return RedirectResponse(url="/", status_code=303)
