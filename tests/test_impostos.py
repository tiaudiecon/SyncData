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


def test_total_ret_sieg_e_a_retencao_real():
    # Total ret. = retenção REAL = Valor_Servico − Valor_Liquido (caso NF 120:
    # serviço 16000, líquido 14536 → retido 1464). CSRF é derivado do total.
    n = NotaSieg("120", "120", "c", "F", None, 16000, 14536, False,
                 iss=480, iss_retido=True, ir=240, pis=600, cofins=500, csll=228)
    assert round(n.total_retencoes, 2) == 1464.0            # 16000 − 14536
    assert round(n.csrf, 2) == 744.0                        # 1464 − 240 − 0 − 480(ISS ret)
    # reconcilia: ISS(retido) + INSS + IRRF + CSRF == Total ret.
    assert round(n.iss + n.inss + n.ir + n.csrf, 2) == n.total_retencoes


def test_iss_nao_retido_fica_fora_do_total():
    # ISS destacado mas NÃO retido: nota sem retenção real → total 0 (caso NF 4117)
    n = NotaSieg("4117", "4117", "c", "F", None, 280, 280, False,
                 iss=8.4, iss_retido=False, ir=0, pis=0, cofins=0, csll=0)
    assert round(n.total_retencoes, 2) == 0.0              # serviço == líquido
    assert round(n.inss + n.ir + n.csrf, 2) == n.total_retencoes  # reconcilia (ISS fora)


def test_impostos_renderiza(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Detalhamento de Impostos" in r.text
    assert "PIS/COFINS/CSLL" in r.text   # nomenclatura DET-04 (era "CSRF")
    assert "IRPJ" in r.text               # DET-04 (era "IRRF")


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


def test_item2_item6_rotulos_novos_na_tela_impostos(client):
    # item 6: "Pendência SIEG" -> "Divergência de Impostos"; item 2: tag "SN".
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Só divergências de impostos" in r.text   # item 6 (chip)
    assert "Div. Impostos" in r.text                  # item 6 (badge/legenda)
    assert "Pendência SIEG" not in r.text             # rótulo antigo sumiu
    assert ">Simples<" not in r.text                  # item 2: agora é "SN"
