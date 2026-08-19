import io
import os
import re
import threading
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.configuracao import esta_configurado, obter_config, contexto_cliente
from app.services.parser_spdata import ler_spdata
from app.services.parser_sieg import ler_sieg
from app.services.renew_runner import contar_pdfs, processar_pasta
from app.services.jobs import criar_job

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    if not esta_configurado(db):
        return RedirectResponse(url="/setup", status_code=303)
    return templates.TemplateResponse(request, "conciliar.html", {
        "ativo": "conciliar", "erro": None, **contexto_cliente(db),
    })


def _erro(request, db, msg):
    return templates.TemplateResponse(request, "conciliar.html", {
        "ativo": "conciliar", "erro": msg, **contexto_cliente(db),
    })


_RX_COMPETENCIA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@router.post("/conciliar")
async def executar(request: Request, db: Session = Depends(get_db),
                   spdata: UploadFile = File(...), sieg: UploadFile = File(...),
                   pasta: str = Form(""), competencia: str = Form("")):
    cfg = obter_config(db)
    competencia = (competencia or "").strip()
    if not _RX_COMPETENCIA.match(competencia):   # INI-02: mês/ano do período
        return _erro(request, db, "Informe a competência (mês/ano) do período.")
    pasta_lim = (pasta or "").strip()
    if not pasta_lim or not os.path.isdir(pasta_lim):
        return _erro(request, db, "Selecione a pasta dos PDFs — o caminho informado não existe.")
    n_pdfs = contar_pdfs(pasta_lim)
    if n_pdfs == 0:
        return _erro(request, db, "A pasta selecionada não tem nenhum PDF.")
    try:
        lancamentos = ler_spdata(await spdata.read())
        autorizadas, canceladas = ler_sieg(io.BytesIO(await sieg.read()), cfg.cnpj_cliente)
    except Exception as exc:   # arquivo trocado/ilegível: avisa na própria tela
        return _erro(request, db, f"Não consegui ler um dos arquivos: {exc}")

    jid = criar_job(total=n_pdfs)
    nomes = {"spdata": spdata.filename, "sieg": sieg.filename, "competencia": competencia}
    threading.Thread(
        target=processar_pasta,
        args=(jid, pasta_lim, autorizadas, canceladas, lancamentos, cfg.cnpj_cliente, nomes),
        daemon=True,
    ).start()
    return templates.TemplateResponse(request, "processando.html", {
        "ativo": "conciliar", "job_id": jid, **contexto_cliente(db),
    })
