import io
import openpyxl
from app.services.exportacao import gerar_xlsx


def _resumo():
    return {"cnpj": "04541288000162", "data_hora": "10/08/2026 10:55",
            "total_universo": 2, "valor_total": 250.0, "qt_gerenciadas": 1,
            "qt_ressalva": 0, "qt_falta_lancar": 1, "qt_falta_arquivar": 1,
            "qt_canceladas": 0}


def _itens():
    return [
        {"numero": "100", "nome_fornecedor": "FORNEC A", "data_emissao": "03/07/2026",
         "valor_bruto": 150.0, "valor_liquido": 150.0, "status_lancamento": "ok",
         "status_arquivo": "ok", "detalhe_lancamento": "", "detalhe_arquivo": "",
         "veredito": "gerenciada"},
        {"numero": "101", "nome_fornecedor": "FORNEC B", "data_emissao": "04/07/2026",
         "valor_bruto": 100.0, "valor_liquido": 100.0, "status_lancamento": "falta",
         "status_arquivo": "falta", "detalhe_lancamento": "", "detalhe_arquivo": "",
         "veredito": "pendente"},
        {"numero": "102", "nome_fornecedor": "FORNEC C", "data_emissao": "05/07/2026",
         "valor_bruto": 200.0, "valor_liquido": 190.0, "status_lancamento": "diverg",
         "status_arquivo": "ok", "detalhe_lancamento": "valor diverge", "detalhe_arquivo": "",
         "veredito": "ressalva"},
    ]


def _itens_ricos():
    base = _itens()
    for it in base:
        it.update({"sieg_bruto": it["valor_bruto"], "sieg_liquido": it["valor_liquido"],
                   "sieg_imp": 0.0, "sp_bruto": it["valor_bruto"],
                   "sp_liquido": it["valor_liquido"], "sp_imp": 0.0, "tem_desconto": False,
                   "impostos": {"sieg": {"iss":0,"inss":0,"ir":0,"csrf":0,"descontos":0,
                                "base_calculo":0,"aliquota":0,"iss_retido":False,"total":0},
                                "spdata": {"iss":0,"inss":0,"ir":0,"csrf":0,"total":0}}})
    return base


def test_export_tem_aba_impostos_e_moeda_numerica():
    import io, openpyxl
    conteudo = gerar_xlsx(_resumo(), _itens_ricos())
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    assert "Impostos" in wb.sheetnames
    ws = wb["Conciliação"]
    # acha uma célula de valor (Bruto Sieg) e confirma que é número com formato moeda
    achou = False
    for row in ws.iter_rows():
        for cel in row:
            if isinstance(cel.value, (int, float)) and "R$" in (cel.number_format or ""):
                achou = True
    assert achou


def test_gera_tres_abas_com_conteudo():
    conteudo = gerar_xlsx(_resumo(), _itens())
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    assert wb.sheetnames == ["Conciliação", "Faltou Lançar", "Faltou Arquivar", "Impostos"]
    # a aba "Faltou Lançar" tem só a nota 101 (1 cabeçalho + 1 linha)
    aba = wb["Faltou Lançar"]
    valores = [c.value for c in aba["A"] if c.value is not None]
    assert "101" in [str(v) for v in valores]
    assert "100" not in [str(v) for v in valores]


def test_faltou_arquivar_contem_so_notas_com_status_arquivo_falta():
    conteudo = gerar_xlsx(_resumo(), _itens())
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    # a aba "Faltou Arquivar" tem só a nota 101 (status_arquivo == "falta")
    aba = wb["Faltou Arquivar"]
    valores = [str(c.value) for c in aba["A"] if c.value is not None]
    assert "101" in valores
    assert "100" not in valores
    assert "102" not in valores


def test_rel02_export_impostos_do_detalhamento():
    from app.services.exportacao import gerar_xlsx_impostos
    conteudo = gerar_xlsx_impostos(_itens_ricos())
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    assert wb.sheetnames == ["Impostos"]
    cab = [c.value for c in wb["Impostos"][1] if c.value]
    assert "IRPJ 1708 (Sieg)" in cab and "PIS/COFINS/CSLL 5952 (Sieg)" in cab


def test_item_com_divergencia_e_exportado_na_aba_conciliacao():
    conteudo = gerar_xlsx(_resumo(), _itens())
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    aba = wb["Conciliação"]
    valores = [str(c.value) for c in aba["A"] if c.value is not None]
    assert "102" in valores
