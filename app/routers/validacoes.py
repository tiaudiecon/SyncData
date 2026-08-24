from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import validacoes as serv

router = APIRouter()


@router.post("/validacoes/marcar")
def marcar(cnpj: str = Form(...), numero: str = Form(...), nome: str = Form(""),
           observacao: str = Form(...), competencia: str = Form(...),
           conciliacao_id: int = Form(...), db: Session = Depends(get_db)):
    """Marca a nota como VALIDADA (sem erro de imposto) a partir do detalhe.
    A nota sai da Divergência de Impostos e passa a contar como Gerenciada —
    apenas nesta competência."""
    serv.salvar(db, competencia.strip(), cnpj, numero, nome.strip(), observacao.strip())
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)


@router.post("/validacoes/desfazer")
def desfazer(cnpj: str = Form(...), numero: str = Form(...),
             competencia: str = Form(...), conciliacao_id: int = Form(...),
             db: Session = Depends(get_db)):
    """Desfaz a validação manual da nota (volta a ser divergência de imposto)."""
    serv.remover(db, competencia.strip(), cnpj, numero)
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)
