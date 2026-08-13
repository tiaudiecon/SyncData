from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ConciliacaoItem

router = APIRouter()


@router.get("/pdf/{item_id}")
def ver_pdf(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ConciliacaoItem).filter(ConciliacaoItem.id == item_id).first()
    if not item or not item.arquivo_pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")
    conc = item.conciliacao
    if not conc or not conc.pasta_pdfs:
        raise HTTPException(status_code=404, detail="Pasta dos PDFs não registrada")
    base = Path(conc.pasta_pdfs).resolve()
    alvo = (base / item.arquivo_pdf).resolve()
    if not alvo.is_relative_to(base) or not alvo.is_file():
        raise HTTPException(status_code=404,
                            detail="PDF não encontrado — a pasta pode ter sido movida.")
    return FileResponse(str(alvo), media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{item.arquivo_pdf}"'})
