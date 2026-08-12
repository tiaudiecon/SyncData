import re


def moeda(v) -> str:
    """Formata número como moeda pt-BR: R$ 1.234,56. '' se não for número."""
    if v is None or v == "":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    s = f"{n:,.2f}"                    # 1,234.56 (estilo en-US)
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s


def largura_numeros(numeros) -> int:
    """Maior quantidade de dígitos entre os números (mínimo 1)."""
    larguras = [len(re.sub(r"\D", "", str(n))) for n in numeros if n]
    return max(larguras) if larguras else 1


def pad_numero(numero, largura) -> str:
    """Preenche com zeros à esquerda até `largura` (números maiores ficam inteiros)."""
    d = re.sub(r"\D", "", str(numero or ""))
    if not d:
        return str(numero or "")
    return d.zfill(largura)


def registrar_filtros(templates):
    """Registra o filtro `moeda` no ambiente Jinja dos templates."""
    templates.env.filters["moeda"] = moeda
