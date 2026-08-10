def formatar_dt(valor):
    """datetime -> 'dd/mm/aaaa HH:MM' (vazio se None)."""
    if not valor:
        return ""
    try:
        return valor.strftime("%d/%m/%Y %H:%M")
    except (AttributeError, ValueError):
        return str(valor)
