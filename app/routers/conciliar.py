from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.configuracao import esta_configurado, obter_config
from app.services.parser_spdata import ler_spdata
from app.services.parser_sieg import ler_sieg
from app.services.parser_renew import ler_renew
from app.services.matcher import conciliar as rodar_conciliacao
from app.services.persistencia import salvar_conciliacao

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _formatar_cnpj(cnpj):
    d = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return cnpj


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    if not esta_configurado(db):
        return RedirectResponse(url="/setup", status_code=303)
    cfg = obter_config(db)
    return templates.TemplateResponse(request, "conciliar.html", {
        "ativo": "conciliar",
        "cnpj_formatado": _formatar_cnpj(cfg.cnpj_cliente),
        "razao": cfg.razao_social, "erro": None,
    })


@router.post("/conciliar")
async def executar(request: Request, db: Session = Depends(get_db),
                   spdata: UploadFile = File(...), sieg: UploadFile = File(...),
                   renew: UploadFile = File(...)):
    import io
    cfg = obter_config(db)
    try:
        lancamentos = ler_spdata(await spdata.read())
        autorizadas, canceladas = ler_sieg(io.BytesIO(await sieg.read()), cfg.cnpj_cliente)
        registros = ler_renew(io.BytesIO(await renew.read()))
    except Exception as exc:  # arquivo trocado/ilegível: mostra na própria tela
        return templates.TemplateResponse(request, "conciliar.html", {
            "ativo": "conciliar",
            "cnpj_formatado": _formatar_cnpj(cfg.cnpj_cliente),
            "razao": cfg.razao_social,
            "erro": f"Não consegui ler um dos arquivos: {exc}",
        })

    resultado = rodar_conciliacao(autorizadas, canceladas, lancamentos, registros)
    conc = salvar_conciliacao(db, cfg.cnpj_cliente, {
        "spdata": spdata.filename, "sieg": sieg.filename, "renew": renew.filename,
    }, resultado)
    return RedirectResponse(url=f"/resultado/{conc.id}", status_code=303)
