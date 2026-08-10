from datetime import date, datetime
from app.services.normalizacao import (
    so_digitos, normalizar_numero_nf, limpar_moeda, para_data, valores_batem,
)


def test_so_digitos_remove_mascara():
    assert so_digitos("39.362.611/0001-15") == "39362611000115"
    assert so_digitos("04541288000162") == "04541288000162"
    assert so_digitos(None) == ""


def test_numero_nf_remove_serie_e_zeros():
    assert normalizar_numero_nf("000972 / 1") == "972"
    assert normalizar_numero_nf("202069 / 7") == "202069"
    assert normalizar_numero_nf("1924136") == "1924136"
    assert normalizar_numero_nf(4291) == "4291"
    assert normalizar_numero_nf(4291.0) == "4291"      # float do openpyxl
    assert normalizar_numero_nf("4291.0") == "4291"    # float já stringificado pelo parser
    assert normalizar_numero_nf("0") == ""      # nota "sem número" (banco)


def test_limpar_moeda_aceita_ponto_e_virgula():
    assert limpar_moeda("2265.57") == 2265.57       # SpData (txt)
    assert limpar_moeda(150) == 150.0               # openpyxl (número)
    assert limpar_moeda("1.234,56") == 1234.56      # eventual formato BR
    assert limpar_moeda(None) == 0.0


def test_para_data_por_dia():
    assert para_data("2015-07-08") == date(2015, 7, 8)
    assert para_data(datetime(2026, 7, 3, 15, 22, 5)) == date(2026, 7, 3)
    assert para_data(None) is None


def test_valores_batem_tolerancia_5_centavos():
    assert valores_batem(150.00, 150.05) is True
    assert valores_batem(150.00, 150.06) is False
    assert valores_batem(1000.00, 1000.00) is True
