import json
from app.models import Conciliacao, ConciliacaoItem


def _fmt_data(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _impostos_json(n, sp):
    dados = {
        "sieg": {"iss": n.iss, "inss": n.inss, "ir": n.ir, "csrf": n.csrf,
                 "descontos": n.descontos, "base_calculo": n.base_calculo,
                 "aliquota": n.aliquota, "iss_retido": n.iss_retido,
                 "optante_sn": n.optante_sn, "total": n.total_retencoes},
        "spdata": ({"iss": sp.issqn, "inss": sp.inss, "ir": sp.ir, "csrf": sp.csrf,
                    "total": sp.total_retencoes} if sp else None),
    }
    return json.dumps(dados)


def salvar_conciliacao(db, cnpj, nomes, resultado):
    """Grava a conciliação (cabeçalho + itens) e devolve o registro."""
    conc = Conciliacao(
        cnpj=cnpj,
        arquivo_spdata_nome=nomes.get("spdata"),
        arquivo_sieg_nome=nomes.get("sieg"),
        arquivo_renew_nome=nomes.get("renew"),
        total_universo=resultado.total_universo,
        valor_total=resultado.valor_total,
        qt_gerenciadas=resultado.qt_gerenciadas,
        qt_ressalva=resultado.qt_ressalva,
        qt_falta_lancar=resultado.qt_falta_lancar,
        qt_falta_arquivar=resultado.qt_falta_arquivar,
        qt_canceladas=resultado.qt_canceladas,
        pasta_pdfs=nomes.get("pasta_pdfs"),
    )
    db.add(conc)
    db.flush()

    for item in resultado.itens:
        n = item.nota
        sp = item.lancamento_row
        db.add(ConciliacaoItem(
            conciliacao_id=conc.id,
            numero=n.numero,
            cnpj_fornecedor=n.cnpj_prestador,
            nome_fornecedor=n.nome_prestador,
            data_emissao=_fmt_data(n.emissao),
            valor_bruto=n.valor_servico,
            valor_liquido=n.valor_liquido,
            sp_valor_bruto=(sp.valor_bruto if sp else None),
            sp_valor_liquido=(sp.valor_liquido if sp else None),
            imp_sieg=n.total_retencoes,
            imp_spdata=(sp.total_retencoes if sp else None),
            tem_desconto=(n.descontos > 0.05),
            impostos_json=_impostos_json(n, sp),
            arquivo_pdf=(item.arquivo_row.arquivo_pdf if item.arquivo_row else None),
            status_lancamento=item.lancamento.status,
            status_arquivo=item.arquivo.status,
            detalhe_lancamento=item.lancamento.detalhe,
            detalhe_arquivo=item.arquivo.detalhe,
            veredito=item.veredito,
            cancelada=False,
        ))

    # notas canceladas (ficam fora do universo/totais, mas gravadas p/ consulta)
    for n in resultado.canceladas:
        db.add(ConciliacaoItem(
            conciliacao_id=conc.id,
            numero=n.numero,
            cnpj_fornecedor=n.cnpj_prestador,
            nome_fornecedor=n.nome_prestador,
            data_emissao=_fmt_data(n.emissao),
            valor_bruto=n.valor_servico,
            valor_liquido=n.valor_liquido,
            imp_sieg=n.total_retencoes,
            impostos_json=_impostos_json(n, None),
            status_lancamento="", status_arquivo="",
            veredito="cancelada",
            cancelada=True,
        ))
    db.commit()
    db.refresh(conc)
    return conc
