import io
import openpyxl
from tests.test_conciliar import _sieg_xlsx, _renew_xlsx, _spdata_txt


def test_resultado_e_export(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"), "application/octet-stream"),
        "renew": ("renew.xlsx", _renew_xlsx(), "application/octet-stream"),
    }, follow_redirects=False)
    destino = resp.headers["location"]                 # /resultado/1
    pagina = client.get(destino)
    assert pagina.status_code == 200
    assert "Gerenciadas" in pagina.text
    planilha = client.get(destino + "/planilha.xlsx")
    assert planilha.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(planilha.content))
    assert wb.sheetnames == ["Conciliação", "Faltou Lançar", "Faltou Arquivar"]
