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


def num_br(v) -> str:
    """Igual a `moeda`, sem o prefixo 'R$ ' — p/ colunas cujo cabeçalho já
    indica que são valores (Bruto/Líq). '' se não for número."""
    s = moeda(v)
    return s[3:] if s.startswith("R$ ") else s


def largura_numeros(numeros) -> int:
    """Largura de padronização = maior quantidade de dígitos entre os números
    (mínimo 1). Todos recebem zeros à esquerda até essa largura, para ficarem
    todos com o mesmo tamanho e alinhados pela direita (pedido do cliente)."""
    larguras = [len(re.sub(r"\D", "", str(n))) for n in numeros if n]
    return max(larguras) if larguras else 1


def pad_numero(numero, largura) -> str:
    """Preenche com zeros à esquerda até `largura` (números maiores ficam inteiros)."""
    d = re.sub(r"\D", "", str(numero or ""))
    if not d:
        return str(numero or "")
    return d.zfill(largura)


def rotular_dv(parte):
    """'bruto R$ x ≠ R$ y' -> 'Bruto: R$ x ≠ R$ y' (rótulo em maiúscula)."""
    cabeca, _sep, resto = (parte or "").partition(" ")
    return (cabeca.capitalize() + ": " + resto) if resto else (parte or "").capitalize()


def registrar_filtros(templates):
    """Registra os filtros de formatação no ambiente Jinja dos templates."""
    templates.env.filters["moeda"] = moeda
    templates.env.filters["num_br"] = num_br
    templates.env.filters["rotular_dv"] = rotular_dv
