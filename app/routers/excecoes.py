from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import excecoes as serv
from app.services.configuracao import contexto_cliente
from app.services.tempo import formatar_dt

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _fmt_cnpj(c):
    d = "".join(ch for ch in str(c or "") if ch.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(c or "")


@router.get("/excecoes")
def tela(request: Request, db: Session = Depends(get_db)):
    linhas = [{
        "id": e.id, "cnpj": _fmt_cnpj(e.cnpj), "nome": e.nome or "",
        "observacao": e.observacao or "", "criado": formatar_dt(e.criado_em),
    } for e in serv.listar(db)]
    return templates.TemplateResponse(request, "excecoes.html", {
        "ativo": "excecoes", "linhas": linhas, **contexto_cliente(db),
    })


@router.post("/excecoes/salvar")
def salvar(cnpj: str = Form(...), nome: str = Form(""), observacao: str = Form(""),
           db: Session = Depends(get_db)):
    serv.salvar(db, cnpj, nome.strip(), observacao.strip())
    return RedirectResponse(url="/excecoes", status_code=303)


@router.post("/excecoes/{id_}/atualizar")
def atualizar(id_: int, nome: str = Form(""), observacao: str = Form(""),
              db: Session = Depends(get_db)):
    serv.atualizar(db, id_, nome.strip(), observacao.strip())
    return RedirectResponse(url="/excecoes", status_code=303)


@router.post("/excecoes/{id_}/remover")
def remover(id_: int, db: Session = Depends(get_db)):
    serv.remover(db, id_)
    return RedirectResponse(url="/excecoes", status_code=303)


@router.post("/excecoes/marcar")
def marcar(cnpj: str = Form(...), nome: str = Form(""), observacao: str = Form(...),
           conciliacao_id: int = Form(...), db: Session = Depends(get_db)):
    """Marca o fornecedor como exceção a partir do detalhe da nota e volta
    para o resultado (a nota — e as futuras do mesmo CNPJ — viram exceção)."""
    serv.salvar(db, cnpj, nome.strip(), observacao.strip())
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)
