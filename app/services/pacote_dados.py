"""Pacote de dados da conciliação (item 3).

Gera um arquivo JSON com o resultado completo da conferência, para o cliente
enviar à contabilidade e o fiscal importar (na v2 multi-tenant). É o formato
nativo do SyncData: autoexplicativo, versionado e com hash de integridade.
"""
import hashlib
import json

FORMATO = "syncdata-conciliacao"
VERSAO = 2


def _situacao(it):
    if it.get("validada"):
        return "validada"
    if it.get("excecao"):
        return "excecao"
    if it.get("cancelada"):
        return "cancelada"
    return it.get("veredito") or ""


def _item(it):
    return {
        "numero": (it.get("numero") or "").strip(),
        "cnpj_fornecedor": it.get("cnpj_fornecedor") or "",
        "nome_fornecedor": it.get("nome_fornecedor") or "",
        "data_emissao": it.get("data_emissao") or "",
        "sieg": {"bruto": it.get("sieg_bruto"), "liquido": it.get("sieg_liquido"),
                 "impostos": it.get("sieg_imp")},
        "spdata": {"bruto": it.get("sp_bruto"), "liquido": it.get("sp_liquido"),
                   "impostos": it.get("sp_imp")},
        "status_lancamento": it.get("status_lancamento") or "",
        "status_arquivo": it.get("status_arquivo") or "",
        "veredito": it.get("veredito") or "",
        "situacao": _situacao(it),
        "gerenciada": bool(it.get("eh_gerenciada")),
        "excecao": ({"observacao": it.get("excecao_obs") or ""} if it.get("excecao") else None),
        "validada": ({"observacao": it.get("validada_obs") or ""} if it.get("validada") else None),
        "optante_sn": bool(it.get("optante_sn")),
        "cancelada": bool(it.get("cancelada")),
        "tipo": ("sp_extra" if it.get("sp_extra") else
                 ("cancelada" if it.get("cancelada") else "sieg")),
        # v2: detalhe completo por nota, p/ importação (SyncData v2 lê o pacote
        # sem precisar reabrir o SIEG/SP Data).
        "impostos": it.get("impostos") or {},
        "detalhe_lancamento": it.get("detalhe_lancamento") or "",
        "detalhe_arquivo": it.get("detalhe_arquivo") or "",
        "tem_desconto": bool(it.get("tem_desconto")),
        "arquivo_pdf": it.get("arquivo_pdf") or "",
    }


def gerar_pacote_dados(resumo, itens, conc):
    corpo = {
        "cliente": {"cnpj": resumo.get("cnpj") or "",
                    "razao_social": resumo.get("razao_social") or ""},
        "competencia": conc.competencia or "",
        "periodo": {"inicio": conc.periodo_inicio or "", "fim": conc.periodo_fim or ""},
        "resumo": {
            "universo": resumo.get("total_universo", 0),
            "valor_total": resumo.get("valor_total", 0.0),
            "gerenciadas": resumo.get("qt_gerenciadas", 0),
            "erros": resumo.get("qt_erros", 0),
            "divergencia_impostos": resumo.get("qt_divergencia", 0),
            "excecoes": resumo.get("qt_excecoes", 0),
            "validadas": resumo.get("qt_validadas", 0),
            "canceladas": resumo.get("qt_canceladas", 0),
            "sp_sem_sieg": resumo.get("qt_sp_sem_sieg", 0),
            "sp_duplicadas": resumo.get("qt_sp_duplicadas", 0),
        },
        "itens": [_item(it) for it in itens],
    }
    # hash de integridade do corpo (detecta adulteração/corrupção no import)
    canonico = json.dumps(corpo, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    corpo_hash = "sha256:" + hashlib.sha256(canonico.encode("utf-8")).hexdigest()
    return {
        "formato": FORMATO,
        "versao": VERSAO,
        "gerado_em": (conc.data_hora.isoformat() if conc.data_hora else ""),
        "hash": corpo_hash,
        **corpo,
    }
