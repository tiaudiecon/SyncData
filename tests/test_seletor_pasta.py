from app.services.seletor_pasta import _parse_saida


def test_parse_pega_o_caminho():
    assert _parse_saida("C:\\Users\\W\\PDFs\n") == r"C:\Users\W\PDFs"


def test_parse_vazio_vira_none():
    assert _parse_saida("") is None
    assert _parse_saida("\n  \n") is None


def test_parse_usa_a_ultima_linha():
    # PowerShell pode imprimir ruído antes; o caminho é a última linha não-vazia.
    assert _parse_saida("aviso\nC:\\PDFs\n") == r"C:\PDFs"
