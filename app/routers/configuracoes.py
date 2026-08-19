from datetime import date
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.configuracao import obter_config, salvar_config, contexto_cliente
from app.services import aliquotas as serv_aliquotas
from app.services.normalizacao import limpar_moeda

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/configuracoes")
def form(request: Request, db: Session = Depends(get_db)):
    cfg = obter_config(db)
    serv_aliquotas.garantir_padrao(db)
    return templates.TemplateResponse(request, "configuracoes.html", {
        "ativo": "config", "cfg": cfg,
        "aliquotas": serv_aliquotas.listar(db),
        "hoje": date.today().isoformat(),
        **contexto_cliente(db),
    })


@router.post("/configuracoes")
def salvar(cnpj: str = Form(...), razao_social: str = Form(""),
           db: Session = Depends(get_db)):
    salvar_config(db, cnpj, razao_social)
    return RedirectResponse(url="/", status_code=303)


@router.post("/configuracoes/aliquotas")
def salvar_aliquotas(vigencia_inicio: str = Form(...), irpj: str = Form(...),
                     pis: str = Form(...), cofins: str = Form(...),
                     csll: str = Form(...), cbs: str = Form("0"),
                     ibs: str = Form("0"), db: Session = Depends(get_db)):
    serv_aliquotas.salvar_vigencia(
        db, vigencia_inicio.strip(),
        limpar_moeda(irpj), limpar_moeda(pis), limpar_moeda(cofins), limpar_moeda(csll),
        limpar_moeda(cbs), limpar_moeda(ibs))       # reforma tributária (prep)
    return RedirectResponse(url="/configuracoes", status_code=303)
