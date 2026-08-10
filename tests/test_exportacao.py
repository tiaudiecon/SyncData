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
    ]


def test_gera_tres_abas_com_conteudo():
    conteudo = gerar_xlsx(_resumo(), _itens())
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    assert wb.sheetnames == ["Conciliação", "Faltou Lançar", "Faltou Arquivar"]
    # a aba "Faltou Lançar" tem só a nota 101 (1 cabeçalho + 1 linha)
    aba = wb["Faltou Lançar"]
    valores = [c.value for c in aba["A"] if c.value is not None]
    assert "101" in [str(v) for v in valores]
    assert "100" not in [str(v) for v in valores]
