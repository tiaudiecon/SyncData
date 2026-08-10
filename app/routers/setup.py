from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.configuracao import salvar_config

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/setup")
def setup_form(request: Request):
    return templates.TemplateResponse("setup.html", {"request": request, "ativo": "config"})


@router.post("/setup")
def setup_salvar(cnpj: str = Form(...), razao_social: str = Form(""),
                 db: Session = Depends(get_db)):
    salvar_config(db, cnpj, razao_social)
    return RedirectResponse(url="/", status_code=303)
