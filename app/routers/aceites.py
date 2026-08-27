from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import aceites as serv

router = APIRouter()


@router.post("/aceites/marcar")
def marcar(cnpj: str = Form(...), numero: str = Form(...), nome: str = Form(""),
           observacao: str = Form(...), competencia: str = Form(...),
           conciliacao_id: int = Form(...), db: Session = Depends(get_db)):
    """Aceita a divergência de valor/arquivo da nota (está correta apesar de não
    bater). A nota sai de Erro e passa a Gerenciada — apenas nesta competência."""
    serv.salvar(db, competencia.strip(), cnpj, numero, nome.strip(), observacao.strip())
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)


@router.post("/aceites/desfazer")
def desfazer(cnpj: str = Form(...), numero: str = Form(...),
             competencia: str = Form(...), conciliacao_id: int = Form(...),
             db: Session = Depends(get_db)):
    """Desfaz o aceite (a nota volta a ser Erro de valor/arquivo)."""
    serv.remover(db, competencia.strip(), cnpj, numero)
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)
