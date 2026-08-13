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


import re
import time
from tests._fakes import pasta_com_pdf, fake_runner
from app.services import renew_runner


def _poll(client, jid, timeout=5.0):
    fim = time.time() + timeout
    ultimo = None
    while time.time() < fim:
        ultimo = client.get(f"/processar/{jid}").json()
        if ultimo.get("fase") in ("pronto", "erro"):
            return ultimo
        time.sleep(0.05)
    return ultimo


def test_fluxo_conciliar_gerenciada(client, monkeypatch):
    monkeypatch.setattr(renew_runner, "rodar_renew", fake_runner)
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar",
                       data={"pasta": pasta_com_pdf()},
                       files={"spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
                              "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"),
                                       "application/octet-stream")})
    assert resp.status_code == 200
    m = re.search(r'data-job="([0-9a-f]+)"', resp.text)
    assert m
    s = _poll(client, m.group(1))
    assert s["fase"] == "pronto"
    assert client.get(f"/resultado/{s['conciliacao_id']}").status_code == 200


def test_arquivo_trocado_no_campo_sieg_mostra_erro_claro(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar",
                       data={"pasta": pasta_com_pdf()},
                       files={"spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
                              "sieg": ("renew.xlsx", _renew_xlsx(),  # arquivo errado
                                       "application/octet-stream")})
    assert resp.status_code == 200
    assert "Não consegui ler" in resp.text


def test_pasta_inexistente_avisa(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar",
                       data={"pasta": r"C:\pasta\que\nao\existe"},
                       files={"spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
                              "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"),
                                       "application/octet-stream")})
    assert resp.status_code == 200
    assert "não existe" in resp.text.lower()
