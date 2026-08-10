from datetime import date
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
