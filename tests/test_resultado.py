import io
import openpyxl
from tests.test_conciliar import _sieg_xlsx, _renew_xlsx, _spdata_txt


def test_montar_itens_enriquecido(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"), "application/octet-stream"),
        "renew": ("renew.xlsx", _renew_xlsx(), "application/octet-stream"),
    }, follow_redirects=False)
    from app.database import SessionLocal
    from app.models import Conciliacao
    from app.routers.resultado import montar_resumo_e_itens
    db = SessionLocal()
    conc = db.query(Conciliacao).order_by(Conciliacao.id.desc()).first()
    resumo, itens = montar_resumo_e_itens(conc)
    db.close()
    assert itens
    it = itens[0]
    for chave in ("sieg_bruto", "sieg_liquido", "sieg_imp", "sp_bruto", "impostos", "tem_desconto"):
        assert chave in it
    assert it["numero"].isdigit()          # nº padronizado (só dígitos)


def test_resultado_tem_busca_e_grupos(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"), "application/octet-stream"),
        "renew": ("renew.xlsx", _renew_xlsx(), "application/octet-stream"),
    }, follow_redirects=False)
    html = client.get(resp.headers["location"]).text
    assert 'id="busca"' in html
    assert "Ver impostos" in html


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
    assert wb.sheetnames == ["Conciliação", "Faltou Lançar", "Faltou Arquivar", "Impostos"]
