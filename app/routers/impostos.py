import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Conciliacao
from app.services.tempo import formatar_dt
from app.services.configuracao import contexto_cliente
from app.services.formatacao import registrar_filtros, largura_numeros, pad_numero

router = APIRouter()
templates = Jinja2Templates(directory="templates")
registrar_filtros(templates)

_TOL = 0.05


def _delta(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 2)


def _linhas(conc):
    largura = largura_numeros([i.numero for i in conc.itens])
    linhas = []
    for i in conc.itens:
        dados = json.loads(i.impostos_json) if i.impostos_json else {}
        s = dados.get("sieg") or {}
        p = dados.get("spdata")
        def par(chave):
            sv = s.get(chave, 0.0)
            pv = (p or {}).get(chave) if p else None
            return {"sieg": sv, "sp": pv, "delta": _delta(sv, pv)}
        linhas.append({
            "numero": pad_numero(i.numero, largura), "nome": i.nome_fornecedor,
            "iss": par("iss"), "inss": par("inss"), "ir": par("ir"), "csrf": par("csrf"),
            "total": par("total"),
            "descontos": s.get("descontos", 0.0), "base": s.get("base_calculo", 0.0),
            "aliquota": s.get("aliquota", 0.0),
        })
    return linhas


def _diverge(linha):
    for k in ("iss", "inss", "ir", "csrf", "total"):
        d = linha[k]["delta"]
        if d is not None and abs(d) > _TOL:
            return True
    return False


@router.get("/impostos")
def mais_recente(request: Request, db: Session = Depends(get_db)):
    conc = db.query(Conciliacao).order_by(Conciliacao.data_hora.desc()).first()
    return _render(request, db, conc)


@router.get("/impostos/{conciliacao_id}")
def por_id(conciliacao_id: int, request: Request, db: Session = Depends(get_db)):
    conc = db.query(Conciliacao).filter(Conciliacao.id == conciliacao_id).first()
    if not conc:
        raise HTTPException(status_code=404, detail="Conciliação não encontrada")
    return _render(request, db, conc)


def _render(request, db, conc):
    linhas = _linhas(conc) if conc else []
    for l in linhas:
        l["diverge"] = _diverge(l)
    return templates.TemplateResponse(request, "impostos.html", {
        "ativo": "impostos", "conc": conc,
        "data_hora": formatar_dt(conc.data_hora) if conc else "",
        "linhas": linhas, **contexto_cliente(db),
    })
