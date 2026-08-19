"""REG-01 — recalcula as retenções esperadas do SIEG pela alíquota base
(REG-02) e sinaliza PENDÊNCIA quando o SIEG apurou valor diferente. Só sinaliza
para análise — não reprova (o cliente pode estar certo, ex.: módulo GRT)."""

LIMITE_DISPENSA = 10.00   # retenção pode ser dispensada quando o valor a reter <= R$ 10,00
_TOL = 0.05


def esperado(base, taxa_pct, optante_sn):
    """Valor esperado da retenção: base × alíquota. Simples Nacional é dispensado (0).
    NÃO zera por causa do limite de R$ 10,00 — a dispensa é uma faculdade, tratada
    no `_diverge` (reter o valor certo continua correto)."""
    if optante_sn:
        return 0.0
    return round((base or 0.0) * (taxa_pct or 0.0) / 100.0, 2)


def _diverge(esp, apurado, optante_sn):
    """True se o SIEG apurou valor incorreto.

    A dispensa de R$ 10,00 é uma FACULDADE do cliente: quando o valor a reter é
    <= R$ 10,00, ele PODE reter o valor certo OU não reter — ambos corretos. Só é
    divergência quando o SIEG foge do esperado E não é uma dispensa legítima."""
    if abs(esp - apurado) <= _TOL:
        return False                                  # reteve o valor certo
    if not optante_sn and apurado <= _TOL and esp <= LIMITE_DISPENSA:
        return False                                  # dispensa exercida (<= R$ 10)
    return True


def pendencia_sieg(sieg, valor_bruto, aliq):
    """`sieg` = dict impostos_json['sieg']; `aliq` = dict vigente (irpj, consolidado).
    Recalcula IRPJ (1708) e PIS/COFINS/CSLL (5952) e compara com o apurado do SIEG.
    Devolve (pendencia: bool, itens: list[{nome, codigo, esperado, apurado}])."""
    if not sieg:
        return False, []
    optsn = bool(sieg.get("optante_sn"))
    base = valor_bruto or 0.0
    checagens = [
        ("IRPJ", "1708", esperado(base, aliq.get("irpj", 0.0), optsn),
         round(sieg.get("ir", 0.0) or 0.0, 2)),
        ("PIS/COFINS/CSLL", "5952", esperado(base, aliq.get("consolidado", 0.0), optsn),
         round(sieg.get("csrf", 0.0) or 0.0, 2)),
    ]
    itens = [{"nome": n, "codigo": c, "esperado": e, "apurado": a}
             for n, c, e, a in checagens if _diverge(e, a, optsn)]
    return (len(itens) > 0), itens
