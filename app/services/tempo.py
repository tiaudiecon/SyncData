def formatar_dt(valor):
    """datetime -> 'dd/mm/aaaa HH:MM' (vazio se None)."""
    if not valor:
        return ""
    try:
        return valor.strftime("%d/%m/%Y %H:%M")
    except (AttributeError, ValueError):
        return str(valor)


_MESES = ("", "jan", "fev", "mar", "abr", "mai", "jun",
          "jul", "ago", "set", "out", "nov", "dez")


def formatar_competencia(valor):
    """INI-02: 'aaaa-mm' -> 'mmm/aaaa' (ex.: '2026-08' -> 'ago/2026').
    Devolve vazio se não vier no formato esperado."""
    try:
        ano, mes = str(valor or "").split("-")
        return f"{_MESES[int(mes)]}/{ano}"
    except (ValueError, IndexError):
        return ""
