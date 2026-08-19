import io
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Conciliacao
import re
from app.services.exportacao import gerar_xlsx
from app.services.tempo import formatar_dt, formatar_competencia
from app.services.configuracao import contexto_cliente, obter_config

router = APIRouter()
templates = Jinja2Templates(directory="templates")
from app.services.formatacao import largura_numeros, pad_numero, registrar_filtros
from app.services import aliquotas as serv_aliquotas
from app.services.recalculo import pendencia_sieg
import json
registrar_filtros(templates)
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_SP_EXTRA = ("sp_sem_sieg", "sp_duplicada")


def _carregar(db, conciliacao_id):
    conc = db.query(Conciliacao).filter(Conciliacao.id == conciliacao_id).first()
    if not conc:
        raise HTTPException(status_code=404, detail="Conciliação não encontrada")
    return conc


def _data_iso(data_br):
    try:
        d, m, a = (data_br or "").split("/")
        return f"{a}-{m.zfill(2)}-{d.zfill(2)}"
    except ValueError:
        return None


def _par(s, p, chave):
    """Par Sieg × SP Data de um tributo (p/ o expand de impostos no Resultado)."""
    sv = s.get(chave, 0.0)
    pv = (p or {}).get(chave) if p else None
    delta = None if (sv is None or pv is None) else round(sv - pv, 2)
    return {"sieg": sv, "sp": pv, "delta": delta}


def montar_resumo_e_itens(conc, tabelas=None):
    tabelas = tabelas or []
    resumo = {
        "cnpj": conc.cnpj, "data_hora": formatar_dt(conc.data_hora),
        "competencia": formatar_competencia(conc.competencia),
        "total_universo": conc.total_universo, "valor_total": conc.valor_total,
        "qt_gerenciadas": conc.qt_gerenciadas, "qt_ressalva": conc.qt_ressalva,
        "qt_falta_lancar": conc.qt_falta_lancar,
        "qt_falta_arquivar": conc.qt_falta_arquivar, "qt_canceladas": conc.qt_canceladas,
        "qt_sp_sem_sieg": sum(1 for i in conc.itens if i.veredito == "sp_sem_sieg"),
        "qt_sp_duplicadas": sum(1 for i in conc.itens if i.veredito == "sp_duplicada"),
    }
    largura = largura_numeros([i.numero for i in conc.itens])
    itens = []
    for i in conc.itens:
        detalhe = "; ".join(d for d in (i.detalhe_lancamento, i.detalhe_arquivo) if d)
        imp = json.loads(i.impostos_json) if i.impostos_json else {}
        sieg_dict = imp.get("sieg") or {}
        sp_dict = imp.get("spdata") or {}
        # CON-05: pendência do SIEG (recálculo) — só p/ notas do SIEG.
        pend, pend_itens = False, []
        if i.veredito not in ("cancelada", *_SP_EXTRA) and sieg_dict:
            aliq = serv_aliquotas.vigente_na_lista(tabelas, _data_iso(i.data_emissao))
            pend, pend_itens = pendencia_sieg(sieg_dict, i.valor_bruto, aliq)
        p_sp = imp.get("spdata")   # None se a nota não foi lançada no SP Data
        itens.append({
            "id": i.id,
            "numero": pad_numero(i.numero, largura),
            "nome_fornecedor": i.nome_fornecedor, "data_emissao": i.data_emissao,
            "sp_data_lancamento": sp_dict.get("data_lancamento", ""),   # CON-01
            "tem_desconto": bool(i.tem_desconto),
            "sieg_bruto": i.valor_bruto, "sieg_liquido": i.valor_liquido,
            "sieg_imp": i.imp_sieg,
            "sp_bruto": i.sp_valor_bruto, "sp_liquido": i.sp_valor_liquido,
            "sp_imp": i.imp_spdata,
            "status_lancamento": i.status_lancamento, "status_arquivo": i.status_arquivo,
            "detalhe": detalhe,
            "detalhe_lancamento": i.detalhe_lancamento or "",
            "detalhe_arquivo": i.detalhe_arquivo or "",
            "veredito": i.veredito, "cancelada": bool(i.cancelada),
            "sp_extra": i.veredito in _SP_EXTRA,          # CON-02/04
            "optante_sn": bool(sieg_dict.get("optante_sn")),   # DET-02 (SN)
            "pendencia_sieg": pend,                        # CON-05
            # item 3: presença em cada sistema (SP Data × SIEG)
            "consta_spdata": i.status_lancamento in ("ok", "diverg"),
            "consta_sieg": i.veredito not in _SP_EXTRA,
            "impostos": imp,
            "arquivo_pdf": i.arquivo_pdf,
            # expand de impostos no Resultado (quebra Sieg × SP Data por tributo)
            "imp_iss": _par(sieg_dict, p_sp, "iss"),
            "imp_inss": _par(sieg_dict, p_sp, "inss"),
            "imp_ir": _par(sieg_dict, p_sp, "ir"),
            "imp_csrf": _par(sieg_dict, p_sp, "csrf"),
            "imp_total": _par(sieg_dict, p_sp, "total"),
            "iss_retido": bool(sieg_dict.get("iss_retido")),
            "imp_descontos": sieg_dict.get("descontos", 0.0),
            "imp_base": sieg_dict.get("base_calculo", 0.0),
            "sem_spdata": p_sp is None,
            "fornecedor_sp": (p_sp or {}).get("fornecedor", ""),
            "pendencia_itens": pend_itens,
        })
    return resumo, itens


@router.get("/resultado/{conciliacao_id}")
def ver(conciliacao_id: int, request: Request, db: Session = Depends(get_db)):
    conc = _carregar(db, conciliacao_id)
    resumo, itens = montar_resumo_e_itens(conc, serv_aliquotas.listar(db))
    return templates.TemplateResponse(request, "resultado.html", {
        "ativo": "resultado", "c": conc,
        "resumo": resumo, "itens": itens, **contexto_cliente(db),
    })


def _nome_arquivo(razao, competencia, conc):
    """SyncData_{empresa}_{competência|data}.xlsx (item 2)."""
    base = re.sub(r"[^A-Za-z0-9]+", "_", (razao or "").strip()).strip("_") or "Cliente"
    quando = competencia or (conc.data_hora.strftime("%Y-%m-%d") if conc.data_hora else "")
    nome = f"SyncData_{base}_{quando}".rstrip("_")
    return nome + ".xlsx"


@router.get("/resultado/{conciliacao_id}/planilha.xlsx")
def baixar(conciliacao_id: int, db: Session = Depends(get_db)):
    conc = _carregar(db, conciliacao_id)
    resumo, itens = montar_resumo_e_itens(conc, serv_aliquotas.listar(db))
    cfg = obter_config(db)
    resumo["razao_social"] = cfg.razao_social or ""      # cabeçalho do relatório
    conteudo = gerar_xlsx(resumo, itens)
    nome = _nome_arquivo(cfg.razao_social, conc.competencia, conc)
    return StreamingResponse(io.BytesIO(conteudo), media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'})
