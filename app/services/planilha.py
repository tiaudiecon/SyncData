import unicodedata
import openpyxl


def norm_texto(txt) -> str:
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def mapa_cabecalho(headers) -> "dict[str, int]":
    return {norm_texto(h): i for i, h in enumerate(headers) if h is not None}


def indice(mapa, *rotulos):
    for rotulo in rotulos:
        i = mapa.get(norm_texto(rotulo))
        if i is not None:
            return i
    return None


def abrir_planilha(arquivo):
    """Abre a 1ª aba em modo read-only/data-only. `arquivo` = caminho ou
    file-like (BytesIO). Retorna (headers:list, linhas:iterador de tuplas)."""
    wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    linhas = ws.iter_rows(values_only=True)
    headers = list(next(linhas, ()) or ())
    return headers, linhas
