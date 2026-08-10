from app.models import Conciliacao, ConciliacaoItem


def _fmt_data(d):
    return d.strftime("%d/%m/%Y") if d else ""


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
    )
    db.add(conc)
    db.flush()  # gera o id

    for item in resultado.itens:
        n = item.nota
        db.add(ConciliacaoItem(
            conciliacao_id=conc.id,
            numero=n.numero,
            cnpj_fornecedor=n.cnpj_prestador,
            nome_fornecedor=n.nome_prestador,
            data_emissao=_fmt_data(n.emissao),
            valor_bruto=n.valor_servico,
            valor_liquido=n.valor_liquido,
            status_lancamento=item.lancamento.status,
            status_arquivo=item.arquivo.status,
            detalhe_lancamento=item.lancamento.detalhe,
            detalhe_arquivo=item.arquivo.detalhe,
            veredito=item.veredito,
            cancelada=False,
        ))
    db.commit()
    db.refresh(conc)
    return conc
