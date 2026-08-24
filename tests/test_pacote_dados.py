from app.services.pacote_dados import gerar_pacote_dados


class _Conc:
    competencia = "2026-07"
    periodo_inicio = "2026-07-01"
    periodo_fim = "2026-07-18"
    data_hora = None


def _resumo():
    return {"cnpj": "04541288000162", "razao_social": "HSS", "total_universo": 2,
            "valor_total": 250.0, "qt_gerenciadas": 2, "qt_erros": 0, "qt_divergencia": 0,
            "qt_excecoes": 0, "qt_validadas": 1, "qt_canceladas": 0,
            "qt_sp_sem_sieg": 0, "qt_sp_duplicadas": 0}


def _itens():
    return [
        {"numero": "100", "cnpj_fornecedor": "11.222.333/0001-99", "nome_fornecedor": "A",
         "data_emissao": "03/07/2026", "sieg_bruto": 150.0, "sieg_liquido": 150.0,
         "sieg_imp": 0.0, "sp_bruto": 150.0, "sp_liquido": 150.0, "sp_imp": 0.0,
         "status_lancamento": "ok", "status_arquivo": "ok", "veredito": "gerenciada",
         "eh_gerenciada": True, "tem_erro": False},
        {"numero": "101", "cnpj_fornecedor": "44.555.666/0001-77", "nome_fornecedor": "B",
         "data_emissao": "04/07/2026", "sieg_bruto": 100.0, "sieg_liquido": 100.0,
         "sieg_imp": 0.0, "sp_bruto": 100.0, "sp_liquido": 100.0, "sp_imp": 0.0,
         "status_lancamento": "ok", "status_arquivo": "ok", "veredito": "gerenciada",
         "eh_gerenciada": True, "tem_erro": False, "validada": True,
         "validada_obs": "conferido"},
    ]


def test_pacote_estrutura_hash_e_situacao():
    p = gerar_pacote_dados(_resumo(), _itens(), _Conc())
    assert p["formato"] == "syncdata-conciliacao" and p["versao"] == 1
    assert p["cliente"]["cnpj"] == "04541288000162"
    assert p["competencia"] == "2026-07" and p["periodo"]["inicio"] == "2026-07-01"
    assert p["resumo"]["gerenciadas"] == 2 and p["resumo"]["erros"] == 0
    assert p["resumo"]["validadas"] == 1
    assert len(p["itens"]) == 2
    assert p["itens"][0]["cnpj_fornecedor"] == "11.222.333/0001-99"
    # a nota validada carrega a situação e a observação
    assert p["itens"][1]["situacao"] == "validada"
    assert p["itens"][1]["validada"]["observacao"] == "conferido"
    assert p["hash"].startswith("sha256:")
