from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import vinculos as serv

router = APIRouter()


@router.post("/vinculos/marcar")
def marcar(cnpj: str = Form(...), numero: str = Form(...), nome: str = Form(""),
           sp_cnpj: str = Form(...), sp_numero: str = Form(""), sp_valor: float = Form(0.0),
           observacao: str = Form(...), competencia: str = Form(...),
           conciliacao_id: int = Form(...), db: Session = Depends(get_db)):
    serv.salvar(db, competencia.strip(), cnpj, numero, nome.strip(),
                sp_cnpj, sp_numero, sp_valor, observacao.strip())
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)


@router.post("/vinculos/desfazer")
def desfazer(cnpj: str = Form(...), numero: str = Form(...), competencia: str = Form(...),
             conciliacao_id: int = Form(...), db: Session = Depends(get_db)):
    serv.remover(db, competencia.strip(), cnpj, numero)
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)
