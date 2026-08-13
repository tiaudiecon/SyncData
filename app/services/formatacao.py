import math
import re


def moeda(v) -> str:
    """Formata número como moeda pt-BR: R$ 1.234,56. '' se não for número."""
    if v is None or v == "":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    if math.isnan(n) or math.isinf(n):   # NaN/Inf também não são "número" exibível
        return ""
    s = f"{n:,.2f}"                    # 1,234.56 (estilo en-US)
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s


_LARGURA_MAX = 6   # teto: números compostos (13 díg.) não puxam todos pra 13 zeros


def largura_numeros(numeros) -> int:
    """Largura de padronização = maior quantidade de dígitos entre os números,
    limitada a `_LARGURA_MAX` (mínimo 1). O teto evita que um número composto de
    13 dígitos transforme '82' em '0000000000082' — fica '000082', e os compostos
    (maiores que o teto) seguem inteiros via `pad_numero`."""
    larguras = [len(re.sub(r"\D", "", str(n))) for n in numeros if n]
    return min(_LARGURA_MAX, max(larguras)) if larguras else 1


def pad_numero(numero, largura) -> str:
    """Preenche com zeros à esquerda até `largura` (números maiores ficam inteiros)."""
    d = re.sub(r"\D", "", str(numero or ""))
    if not d:
        return str(numero or "")
    return d.zfill(largura)


def registrar_filtros(templates):
    """Registra o filtro `moeda` no ambiente Jinja dos templates."""
    templates.env.filters["moeda"] = moeda
