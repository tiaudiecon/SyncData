"""REG-01 — recalcula as retenções esperadas do SIEG pela alíquota base
(REG-02) e sinaliza PENDÊNCIA quando o SIEG apurou valor diferente. Só sinaliza
para análise — não reprova (o cliente pode estar certo, ex.: módulo GRT)."""

LIMITE_DISPENSA = 10.00   # retenção dispensada quando o valor a reter <= R$ 10,00


def esperado(base, taxa_pct, optante_sn):
    """Valor esperado da retenção: base × alíquota. Simples Nacional é dispensado
    (0); abaixo do limite de dispensa (R$ 10,00) também vira 0."""
    if optante_sn:
        return 0.0
    v = round((base or 0.0) * (taxa_pct or 0.0) / 100.0, 2)
    return 0.0 if v <= LIMITE_DISPENSA else v


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
             for n, c, e, a in checagens if abs(e - a) > 0.05]
    return (len(itens) > 0), itens
