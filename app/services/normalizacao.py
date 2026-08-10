import re
from datetime import date, datetime

TOLERANCIA_VALOR = 0.05


def so_digitos(valor) -> str:
    """CNPJ/CPF só com dígitos (remove ./-/ espaços). '' se vazio."""
    return re.sub(r"\D", "", str(valor or ""))


def normalizar_numero_nf(valor) -> str:
    """Número da NF para comparação: parte antes de '/', só dígitos, sem zeros
    à esquerda. '0'/'000' viram '' (lançamento sem nota fiscal).

    Divide também no '.' porque um número inteiro pode chegar como float — do
    openpyxl (4291.0) ou já stringificado pelo parser ('4291.0'); sem isto o
    '.0' viraria '42910' e a nota nunca casaria. Nº de NFS-e é sempre inteiro."""
    texto = str(valor if valor is not None else "").split("/")[0].split(".")[0]
    digitos = re.sub(r"\D", "", texto).lstrip("0")
    return digitos


def limpar_moeda(valor) -> float:
    """Converte para float. Aceita número (openpyxl), '2265.57' (SpData) e
    '1.234,56' (formato BR). Arredonda em 2 casas."""
    if valor is None or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return round(float(valor), 2)
    s = str(valor).strip().replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def para_data(valor):
    """datetime/date/'AAAA-MM-DD' -> date (por dia). None se vazio/inválido."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None


def valores_batem(a, b, tolerancia=TOLERANCIA_VALOR) -> bool:
    """True se |a-b| <= tolerância (R$ 0,05 por padrão)."""
    return abs(float(a) - float(b)) <= tolerancia + 1e-9
