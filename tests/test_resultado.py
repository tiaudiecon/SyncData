import io
import openpyxl
from tests.test_conciliar import _sieg_xlsx, _spdata_txt
from tests._fakes import montar_conciliacao


def test_montar_itens_enriquecido(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
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
    assert it["numero"].isdigit()


def test_resultado_tem_busca_e_grupos(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    html = client.get(f"/resultado/{st['conciliacao_id']}").text
    assert 'id="busca"' in html
    assert "Ver impostos" in html


def test_resultado_mostra_botao_pdf(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    html = client.get(f"/resultado/{st['conciliacao_id']}").text
    assert "/pdf/" in html
    assert "Abrir" in html


def test_item3_selos_presenca_spdata_e_sieg(client):
    # item 3: coluna Lançam. traz dois selos (SP Data e SIEG), verde=consta.
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    html = client.get(f"/resultado/{st['conciliacao_id']}").text
    assert "selo-sis" in html and "SP Data" in html and "SIEG" in html
    from app.database import SessionLocal
    from app.models import Conciliacao
    from app.routers.resultado import montar_resumo_e_itens
    db = SessionLocal()
    conc = db.query(Conciliacao).order_by(Conciliacao.id.desc()).first()
    _, itens = montar_resumo_e_itens(conc)
    db.close()
    for chave in ("consta_spdata", "consta_sieg", "optante_sn"):
        assert chave in itens[0]


def test_item6_renomeia_pendencia_para_divergencia_impostos(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    html = client.get(f"/resultado/{st['conciliacao_id']}").text
    assert "Divergência Impostos" in html
    assert "Pendência SIEG" not in html and "SIEG?" not in html


def test_resultado_e_export(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    destino = f"/resultado/{st['conciliacao_id']}"
    assert client.get(destino).status_code == 200
    planilha = client.get(destino + "/planilha.xlsx")
    assert planilha.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(planilha.content))
    assert wb.sheetnames == ["Conciliação", "Faltou Lançar", "Faltou Arquivar", "Impostos"]
