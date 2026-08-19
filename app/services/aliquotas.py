"""Alíquotas base de retenção (REG-02) — parametrizáveis, com vigência por
período. Valores em % (ex.: 1.50 = 1,50%)."""
from datetime import date
from app.models import TabelaAliquota

# Padrão informado pelo Fiscal (18/08/2026).
PADRAO = {"irpj": 1.50, "pis": 0.65, "cofins": 3.00, "csll": 1.00}
_VIGENCIA_PADRAO = "2026-01-01"


def garantir_padrao(db):
    """Cria a tabela padrão na primeira vez (idempotente)."""
    if db.query(TabelaAliquota).count() == 0:
        db.add(TabelaAliquota(vigencia_inicio=_VIGENCIA_PADRAO, **PADRAO))
        db.commit()


def listar(db):
    return (db.query(TabelaAliquota)
              .order_by(TabelaAliquota.vigencia_inicio.desc()).all())


def _to_dict(t):
    return {
        "vigencia_inicio": t.vigencia_inicio, "irpj": t.irpj, "pis": t.pis,
        "cofins": t.cofins, "csll": t.csll,
        "cbs": (t.cbs or 0.0), "ibs": (t.ibs or 0.0),   # reforma tributária (prep)
        "consolidado": round((t.pis or 0) + (t.cofins or 0) + (t.csll or 0), 2),
    }


def _padrao_dict():
    return dict(PADRAO, vigencia_inicio=_VIGENCIA_PADRAO,
                consolidado=round(PADRAO["pis"] + PADRAO["cofins"] + PADRAO["csll"], 2))


def vigente_na_lista(tabelas, data_ref):
    """Escolhe a vigente numa lista já carregada (ordenada desc por vigência),
    evitando uma query por nota. `data_ref` = 'aaaa-mm-dd' ou None."""
    ref = data_ref or date.today().isoformat()
    for t in tabelas:
        if t.vigencia_inicio <= ref:
            return _to_dict(t)
    return _to_dict(tabelas[-1]) if tabelas else _padrao_dict()


def vigente(db, data_ref=None):
    """Tabela vigente na data (aaaa-mm-dd); a mais recente ≤ data."""
    return vigente_na_lista(listar(db), data_ref)


def salvar_vigencia(db, vigencia_inicio, irpj, pis, cofins, csll, cbs=0.0, ibs=0.0):
    """Cria ou atualiza a tabela daquela vigência."""
    existente = (db.query(TabelaAliquota)
                   .filter_by(vigencia_inicio=vigencia_inicio).first())
    if existente:
        existente.irpj, existente.pis = irpj, pis
        existente.cofins, existente.csll = cofins, csll
        existente.cbs, existente.ibs = cbs, ibs
    else:
        db.add(TabelaAliquota(vigencia_inicio=vigencia_inicio, irpj=irpj,
                              pis=pis, cofins=cofins, csll=csll, cbs=cbs, ibs=ibs))
    db.commit()
