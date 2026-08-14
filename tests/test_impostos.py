from tests.test_conciliar import _sieg_xlsx, _spdata_txt
from tests._fakes import montar_conciliacao
from app.routers.impostos import _diverge
from app.services.parser_sieg import NotaSieg


def _linha_delta(iss, csrf, total, iss_retido):
    return {"iss": {"delta": iss}, "inss": {"delta": 0.0}, "ir": {"delta": 0.0},
            "csrf": {"delta": csrf}, "total": {"delta": total}, "iss_retido": iss_retido}


def test_iss_informativo_nao_conta_como_divergencia():
    # só o ISS difere (13,50 × 0), mas NÃO é retido → informativo → não diverge
    assert _diverge(_linha_delta(13.5, 0.0, 0.0, iss_retido=False)) is False


def test_iss_retido_conta_como_divergencia():
    # mesmo caso, porém ISS RETIDO → é retenção de verdade → diverge
    assert _diverge(_linha_delta(13.5, 0.0, 13.5, iss_retido=True)) is True


def test_csrf_diverge_sempre_conta():
    # CSRF diverge independe do ISS
    assert _diverge(_linha_delta(0.0, 300.0, 300.0, iss_retido=False)) is True


def test_total_ret_sieg_reconcilia_com_as_linhas():
    # o Total ret. do Sieg = ISS(se retido) + INSS + IR + CSRF + OutRetencoes;
    # sem a linha "Outras ret." o discriminado não fecha com o total (caso NF 120).
    n = NotaSieg("120", "120", "c", "F", None, 20000, 16000, False,
                 iss=480, iss_retido=True, ir=240, pis=600, cofins=500, csll=228,
                 outret=1464)
    assert round(n.csrf, 2) == 1328.0
    assert round(n.total_retencoes, 2) == 3512.0
    assert round(n.iss + n.inss + n.ir + n.csrf + n.outret, 2) == n.total_retencoes


def test_iss_nao_retido_fica_fora_do_total():
    # ISS destacado mas NÃO retido não entra no total (caso NF 4117)
    n = NotaSieg("4117", "4117", "c", "F", None, 280, 280, False,
                 iss=8.4, iss_retido=False, ir=0, pis=0, cofins=0, csll=0, outret=0)
    assert round(n.total_retencoes, 2) == 0.0
    # sem o ISS informativo, as linhas de retenção somam o total
    assert round(n.inss + n.ir + n.csrf + n.outret, 2) == n.total_retencoes


def test_impostos_renderiza(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Detalhamento de Impostos" in r.text
    assert "CSRF" in r.text


def _spdata_nota_diferente():
    # SPData com uma nota (999) que NÃO casa com a do Sieg (100) -> nota do Sieg
    # fica sem lançamento no SPData ("faltou lançar").
    cab = ("EMISSAO|ENTRADA|NOTA|CNPJ_CPF|FORNECEDOR|ORIGEM|VALOR_BRUTO|VALOR_LIQUIDO|"
           "IR_COOP|IRPJ|IR_AUTON|CSRF|INSS_PJ|INSS_AUTON|ISSQN|GRUPO|DESC_GRUPO|"
           "SUBGRUPO|DESC_SUBGRUPO|ITEM|DESC_ITEM")
    linha = ("2026-07-03|2026-07-03|999|11111111000111|OUTRO|FIN|10.00|10.00|"
             "0|0|0|0|0|0|0|103|MAT|1|SUB|2|IT")
    return (cab + "\n" + linha + "\n").encode("cp1252")


def test_nota_sem_spdata_mostra_sem_spdata_nao_ok(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    montar_conciliacao("04541288000162", _spdata_nota_diferente(),
                       _sieg_xlsx("04541288000162"))
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Sem SPData" in r.text   # não pode marcar OK sem dados do SPData


def test_impostos_vazio_sem_conciliacao(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Nenhuma conciliação" in r.text
