from app.services.formatacao import moeda, largura_numeros, pad_numero, registrar_filtros


def test_moeda_pt_br():
    assert moeda(1234.56) == "R$ 1.234,56"
    assert moeda(800.92) == "R$ 800,92"
    assert moeda(0) == "R$ 0,00"
    assert moeda(1234567.8) == "R$ 1.234.567,80"
    assert moeda(None) == ""


def test_moeda_nao_numerico_vira_vazio():
    assert moeda("abc") == ""
    assert moeda(float("nan")) == ""
    assert moeda(float("inf")) == ""


def test_registrar_filtros():
    from fastapi.templating import Jinja2Templates
    t = Jinja2Templates(directory="templates")
    registrar_filtros(t)
    assert t.env.filters["moeda"] is moeda


def test_padronizacao_pelo_maior():
    nums = ["18", "2098", "202069"]
    L = largura_numeros(nums)
    assert L == 6
    assert pad_numero("18", L) == "000018"
    assert pad_numero("202069", L) == "202069"
    assert pad_numero("2600000002098", L) == "2600000002098"  # maior que L: inteiro


def test_largura_padroniza_pelo_maior_inclusive_composto():
    # Alinhamento pela direita: TODOS recebem zeros até a largura do MAIOR número.
    L = largura_numeros(["82", "2026000000018"])
    assert L == 13
    assert pad_numero("82", L) == "0000000000082"
    assert pad_numero("2026000000018", L) == "2026000000018"
