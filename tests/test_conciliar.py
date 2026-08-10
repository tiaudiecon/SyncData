import io
import openpyxl


def _sieg_xlsx(cnpj_cliente):
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Numero", "Dt_Emissao", "Prestador", "RzPrestador", "Tomador",
               "Valor_Servico", "Valor_Liquido", "Dt_Cancelamento", "Status"])
    from datetime import datetime
    ws.append(["100", datetime(2026, 7, 3), "11111111000111", "FORNEC A",
               cnpj_cliente, 150, 150, None, "Autorizado o uso da NFS-e"])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def _renew_xlsx():
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Status", "Tipo de Nota", "Nome Original", "Novo Nome",
               "Fornecedor Emitente", "CNPJ do Emissor", "Nº NF / Série",
               "Data de Emissão", "Valor da NF"])
    from datetime import datetime
    ws.append(["OK", "SERVICO", "x", "x", "FORNEC A", "11.111.111/0001-11",
               "100", datetime(2026, 7, 3), 150])
    buf = io.BytesIO(); wb.save(buf); return buf.getvalue()


def _spdata_txt():
    cab = ("EMISSAO|ENTRADA|NOTA|CNPJ_CPF|FORNECEDOR|ORIGEM|VALOR_BRUTO|VALOR_LIQUIDO|"
           "IR_COOP|IRPJ|IR_AUTON|CSRF|INSS_PJ|INSS_AUTON|ISSQN|GRUPO|DESC_GRUPO|"
           "SUBGRUPO|DESC_SUBGRUPO|ITEM|DESC_ITEM")
    linha = ("2026-07-03|2026-07-03|100|11111111000111|FORNEC A|FIN|150.00|150.00|"
             "0|0|0|0|0|0|0|103|MAT|1|SUB|2|IT")
    return (cab + "\n" + linha + "\n").encode("cp1252")


def test_fluxo_conciliar_gerenciada(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"),
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "renew": ("renew.xlsx", _renew_xlsx(),
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/resultado/")


def test_arquivo_trocado_no_campo_sieg_mostra_erro_claro(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("renew.xlsx", _renew_xlsx(),  # arquivo errado no campo do Sieg
                 "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "renew": ("renew.xlsx", _renew_xlsx(),
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }, follow_redirects=False)
    assert resp.status_code == 200
    assert "Não consegui ler" in resp.text
