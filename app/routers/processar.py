from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.services.jobs import estado
from app.services.seletor_pasta import escolher_pasta

router = APIRouter()


@router.get("/procurar-pasta")
def procurar_pasta():
    return JSONResponse({"pasta": escolher_pasta()})


@router.get("/processar/{job_id}")
def status_job(job_id: str):
    s = estado(job_id)
    if s is None:
        return JSONResponse({"erro": "job desconhecido"}, status_code=404)
    return JSONResponse(s)
