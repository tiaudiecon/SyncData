import io
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Conciliacao
from app.services.exportacao import gerar_xlsx
from app.services.tempo import formatar_dt
from app.services.configuracao import contexto_cliente

router = APIRouter()
templates = Jinja2Templates(directory="templates")
from app.services.formatacao import largura_numeros, pad_numero, registrar_filtros
import json
registrar_filtros(templates)
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _carregar(db, conciliacao_id):
    conc = db.query(Conciliacao).filter(Conciliacao.id == conciliacao_id).first()
    if not conc:
        raise HTTPException(status_code=404, detail="Conciliação não encontrada")
    return conc


def montar_resumo_e_itens(conc):
    resumo = {
        "cnpj": conc.cnpj, "data_hora": formatar_dt(conc.data_hora),
        "total_universo": conc.total_universo, "valor_total": conc.valor_total,
        "qt_gerenciadas": conc.qt_gerenciadas, "qt_ressalva": conc.qt_ressalva,
        "qt_falta_lancar": conc.qt_falta_lancar,
        "qt_falta_arquivar": conc.qt_falta_arquivar, "qt_canceladas": conc.qt_canceladas,
    }
    largura = largura_numeros([i.numero for i in conc.itens])
    itens = []
    for i in conc.itens:
        detalhe = "; ".join(d for d in (i.detalhe_lancamento, i.detalhe_arquivo) if d)
        itens.append({
            "id": i.id,
            "numero": pad_numero(i.numero, largura),
            "nome_fornecedor": i.nome_fornecedor, "data_emissao": i.data_emissao,
            "tem_desconto": bool(i.tem_desconto),
            "sieg_bruto": i.valor_bruto, "sieg_liquido": i.valor_liquido,
            "sieg_imp": i.imp_sieg,
            "sp_bruto": i.sp_valor_bruto, "sp_liquido": i.sp_valor_liquido,
            "sp_imp": i.imp_spdata,
            "status_lancamento": i.status_lancamento, "status_arquivo": i.status_arquivo,
            "detalhe": detalhe,
            "detalhe_lancamento": i.detalhe_lancamento or "",
            "detalhe_arquivo": i.detalhe_arquivo or "",
            "veredito": i.veredito,
            "impostos": json.loads(i.impostos_json) if i.impostos_json else {},
            "arquivo_pdf": i.arquivo_pdf,
        })
    return resumo, itens


@router.get("/resultado/{conciliacao_id}")
def ver(conciliacao_id: int, request: Request, db: Session = Depends(get_db)):
    conc = _carregar(db, conciliacao_id)
    resumo, itens = montar_resumo_e_itens(conc)
    return templates.TemplateResponse(request, "resultado.html", {
        "ativo": "conciliar", "c": conc,
        "resumo": resumo, "itens": itens, **contexto_cliente(db),
    })


@router.get("/resultado/{conciliacao_id}/planilha.xlsx")
def baixar(conciliacao_id: int, db: Session = Depends(get_db)):
    conc = _carregar(db, conciliacao_id)
    resumo, itens = montar_resumo_e_itens(conc)
    conteudo = gerar_xlsx(resumo, itens)
    nome = f"SyncData_{conc.cnpj}_{conc.id}.xlsx"
    return StreamingResponse(io.BytesIO(conteudo), media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'})
