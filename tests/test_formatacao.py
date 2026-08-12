from app.services.formatacao import moeda, largura_numeros, pad_numero


def test_moeda_pt_br():
    assert moeda(1234.56) == "R$ 1.234,56"
    assert moeda(800.92) == "R$ 800,92"
    assert moeda(0) == "R$ 0,00"
    assert moeda(1234567.8) == "R$ 1.234.567,80"
    assert moeda(None) == ""


def test_padronizacao_pelo_maior():
    nums = ["18", "2098", "202069"]
    L = largura_numeros(nums)
    assert L == 6
    assert pad_numero("18", L) == "000018"
    assert pad_numero("202069", L) == "202069"
    assert pad_numero("2600000002098", L) == "2600000002098"  # maior que L: inteiro
