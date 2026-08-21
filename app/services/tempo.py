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


def formatar_data_br(iso):
    """'aaaa-mm-dd' -> 'dd/mm/aaaa' (vazio se não vier no formato esperado)."""
    try:
        ano, mes, dia = str(iso or "").split("-")
        if len(ano) == 4:
            return f"{dia.zfill(2)}/{mes.zfill(2)}/{ano}"
    except ValueError:
        pass
    return ""


def formatar_periodo(inicio, fim):
    """Período da conferência: 'dd/mm/aaaa a dd/mm/aaaa' (o que houver)."""
    di, df = formatar_data_br(inicio), formatar_data_br(fim)
    if di and df:
        return f"{di} a {df}"
    return di or df or ""
