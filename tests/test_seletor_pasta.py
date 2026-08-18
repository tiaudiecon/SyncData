from app.services.seletor_pasta import _PS, _parse_saida


def test_parse_pega_o_caminho():
    assert _parse_saida("C:\\Users\\W\\PDFs\n") == r"C:\Users\W\PDFs"


def test_parse_aceita_caminho_de_rede_unc():
    # INI-01: o seletor deve devolver caminhos de rede/UNC intactos.
    assert _parse_saida("\\\\marte\\Audiecon\\PDFs\n") == r"\\marte\Audiecon\PDFs"


def test_ini01_usa_o_diALogo_moderno_com_fallback():
    # Diálogo moderno (enxerga rede/UNC): FileOpenDialog + FOS_PICKFOLDERS.
    assert "DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7" in _PS
    assert "SyncDataFolderPicker" in _PS and "0x60" in _PS
    # Fallback pro clássico se o moderno falhar.
    assert "FolderBrowserDialog" in _PS


def test_parse_vazio_vira_none():
    assert _parse_saida("") is None
    assert _parse_saida("\n  \n") is None


def test_parse_usa_a_ultima_linha():
    # PowerShell pode imprimir ruído antes; o caminho é a última linha não-vazia.
    assert _parse_saida("aviso\nC:\\PDFs\n") == r"C:\PDFs"
