from datetime import date
import pytest
from app.services.parser_spdata import ler_spdata, LancamentoSpData

CABECALHO = ("EMISSAO|ENTRADA|NOTA|CNPJ_CPF|FORNECEDOR|ORIGEM|VALOR_BRUTO|"
             "VALOR_LIQUIDO|IR_COOP|IRPJ|IR_AUTON|CSRF|INSS_PJ|INSS_AUTON|"
             "ISSQN|GRUPO|DESC_GRUPO|SUBGRUPO|DESC_SUBGRUPO|ITEM|DESC_ITEM")


def _linha(emissao, nota, cnpj, fornecedor, bruto, liquido):
    return (f"{emissao}|{emissao}|{nota}|{cnpj}|{fornecedor}|FIN|{bruto}|"
            f"{liquido}|0.00|0.00|0.00|0.00|0.00|0.00|0.00|103|MAT|1|SUB|2|IT")


def _arquivo(*linhas):
    return ("\n".join([CABECALHO, *linhas]) + "\n").encode("cp1252")


def test_le_campos_essenciais():
    conteudo = _arquivo(
        _linha("2015-07-08", "21911", "07876749000146", "GIROFARMA LTDA", "2265.57", "2265.57"),
    )
    itens = ler_spdata(conteudo)
    assert len(itens) == 1
    it = itens[0]
    assert isinstance(it, LancamentoSpData)
    assert it.numero == "21911"
    assert it.numero_norm == "21911"
    assert it.cnpj == "07876749000146"
    assert it.fornecedor == "GIROFARMA LTDA"
    assert it.emissao == date(2015, 7, 8)
    assert it.valor_bruto == 2265.57
    assert it.valor_liquido == 2265.57


def test_encoding_latin1_preserva_acentos():
    conteudo = _arquivo(
        _linha("2017-05-31", "11", "18065112000196", "LIFEODONTO BRAGANÇA", "850.00", "850.00"),
    )
    assert ler_spdata(conteudo)[0].fornecedor == "LIFEODONTO BRAGANÇA"


def test_ignora_linhas_vazias():
    conteudo = _arquivo(
        _linha("2017-04-06", "0", "17103433000175", "IPE PETROLEO", "50.00", "50.00"),
        "",
    )
    itens = ler_spdata(conteudo)
    assert len(itens) == 1
    assert itens[0].numero_norm == ""   # NOTA=0 vira "" (sem nota)


def test_coluna_obrigatoria_faltando_gera_erro_claro():
    cabecalho_sem_nota = ("EMISSAO|ENTRADA|CNPJ_CPF|FORNECEDOR|ORIGEM|VALOR_BRUTO|"
                          "VALOR_LIQUIDO|IR_COOP|IRPJ|IR_AUTON|CSRF|INSS_PJ|INSS_AUTON|"
                          "ISSQN|GRUPO|DESC_GRUPO|SUBGRUPO|DESC_SUBGRUPO|ITEM|DESC_ITEM")
    linha = ("2015-07-08|2015-07-08|07876749000146|GIROFARMA LTDA|FIN|2265.57|2265.57|"
             "0.00|0.00|0.00|0.00|0.00|0.00|0.00|103|MAT|1|SUB|2|IT")
    conteudo = (cabecalho_sem_nota + "\n" + linha + "\n").encode("cp1252")

    with pytest.raises(ValueError, match="NOTA"):
        ler_spdata(conteudo)


def test_captura_impostos_spdata():
    # F&P: IRPJ 308,70 / CSRF 956,97 (a coluna CSRF do SPData)
    cab = ("EMISSAO|ENTRADA|NOTA|CNPJ_CPF|FORNECEDOR|ORIGEM|VALOR_BRUTO|VALOR_LIQUIDO|"
           "IR_COOP|IRPJ|IR_AUTON|CSRF|INSS_PJ|INSS_AUTON|ISSQN|GRUPO|DESC_GRUPO|"
           "SUBGRUPO|DESC_SUBGRUPO|ITEM|DESC_ITEM")
    linha = ("2026-07-17|2026-07-17|18|30590469000199|F E P|GRT|20580.00|19314.33|"
             "0.00|308.70|0.00|956.97|0.00|0.00|0.00|1|G|1|S|1|I")
    conteudo = (cab + "\n" + linha + "\n").encode("cp1252")
    it = ler_spdata(conteudo)[0]
    assert it.irpj == 308.70
    assert it.csrf == 956.97
    assert it.ir == 308.70               # IRPJ+IR_AUTON+IR_COOP
    assert it.inss == 0.0
    assert round(it.total_retencoes, 2) == round(308.70 + 956.97, 2)  # ISSQN+INSS+IR+CSRF
