from dataclasses import dataclass, field
from app.services.normalizacao import valores_batem
from app.services.formatacao import moeda

STATUS_OK = "ok"
STATUS_DIVERG = "diverg"
STATUS_FALTA = "falta"


@dataclass
class Frente:
    status: str
    detalhe: str = ""


@dataclass
class ItemConciliacao:
    nota: object
    lancamento: Frente
    arquivo: Frente
    veredito: str = "pendente"
    lancamento_row: object = None
    arquivo_row: object = None


@dataclass
class ResultadoConciliacao:
    itens: list = field(default_factory=list)
    canceladas: list = field(default_factory=list)
    sp_sem_sieg: list = field(default_factory=list)     # CON-02/03: no SP Data, sem SIEG
    sp_duplicadas: list = field(default_factory=list)   # CON-04: duplicadas no SP Data
    total_universo: int = 0
    valor_total: float = 0.0
    qt_gerenciadas: int = 0
    qt_ressalva: int = 0
    qt_falta_lancar: int = 0
    qt_falta_arquivar: int = 0
    qt_canceladas: int = 0
    qt_sp_sem_sieg: int = 0
    qt_sp_duplicadas: int = 0


def _fmt_data(d):
    return d.strftime("%d/%m/%Y") if d else "—"


def _indexar_por_cnpj(itens, get_cnpj):
    idx = {}
    for it in itens:
        idx.setdefault(get_cnpj(it), []).append(it)
    return idx


_MIN_PREFIXO_COMPOSTO = 6


def _casa_numero(a, b):
    """Números casam quando são iguais, ou — caso de número composto — quando o
    número longo (Sieg/Renew trazem um código com prefixo, ex.: '2026000000018')
    termina no número curto do SpData (ex.: '18'). Só vale como composto se o
    longo for MUITO maior que o curto (prefixo de ≥6 dígitos), o que libera os
    compostos reais e barra coincidência de números curtos ('5' × '125'). O
    valor é sempre conferido por quem chama, como guarda final."""
    if not a or not b:
        return False
    if a == b:
        return True
    curto, longo = (a, b) if len(a) <= len(b) else (b, a)
    return len(longo) - len(curto) >= _MIN_PREFIXO_COMPOSTO and longo.endswith(curto)


def _avaliar(nota, candidatos_cnpj, comparar):
    """`candidatos_cnpj` = itens do MESMO CNPJ do fornecedor. Casa por número: o
    número exato tem prioridade (aí valor/data/impostos entram como conferência →
    🟢/🟡); sem número exato, tenta o número composto por sufixo (`_casa_numero`),
    que só vale como a mesma nota quando a IDENTIDADE bate (bruto+líquido; guarda
    contra falso-positivo) — aí impostos/data ainda podem gerar divergência.
    `comparar(nota, cand) -> (data_ok, ident_ok, full_ok, detalhe)`, onde
    `ident_ok` = é a mesma nota (bruto+líquido/valor) e `full_ok` = tudo confere.
    Devolve (Frente, candidato_casado_ou_None)."""
    if not candidatos_cnpj:
        return Frente(STATUS_FALTA, ""), None

    exatos = [c for c in candidatos_cnpj
              if nota.numero_norm and c.numero_norm == nota.numero_norm]
    if exatos:
        melhor = None
        for c in exatos:
            data_ok, _ident_ok, full_ok, detalhe = comparar(nota, c)
            if data_ok and full_ok:
                return Frente(STATUS_OK, ""), c
            acertos = int(data_ok) + int(full_ok)
            if melhor is None or acertos > melhor[0]:
                melhor = (acertos, detalhe, c)
        return Frente(STATUS_DIVERG, melhor[1]), melhor[2]

    for c in candidatos_cnpj:
        if _casa_numero(nota.numero_norm, c.numero_norm):
            data_ok, ident_ok, full_ok, detalhe = comparar(nota, c)
            if ident_ok:   # número composto + identidade forte = a mesma nota
                if data_ok and full_ok:
                    return Frente(STATUS_OK, ""), c
                return Frente(STATUS_DIVERG, detalhe), c
    return Frente(STATUS_FALTA, ""), None


def _cmp_spdata(nota, c):
    # A data do SpData é a de LANÇAMENTO (= coluna ENTRADA), não a de emissão da
    # NF, então NÃO comparamos data nesta frente (data_ok=True sempre). Comparamos
    # bruto, líquido e IMPOSTOS (retenções). Bruto+líquido definem a IDENTIDADE da
    # nota; os impostos entram como conferência adicional (divergência, não
    # "faltou"). A retenção do Sieg é base−líquido (base = bruto já sem desconto),
    # pois o DESCONTO não é retenção — só assim uma nota com desconto não diverge.
    bruto_ok = valores_batem(nota.bruto_ajustado, c.valor_bruto)
    liq_ok = valores_batem(nota.valor_liquido, c.valor_liquido)
    ret_sieg = round(max(0.0, nota.bruto_ajustado - nota.valor_liquido), 2)
    imp_ok = valores_batem(ret_sieg, c.total_retencoes)
    partes = []
    if not bruto_ok:
        partes.append(f"bruto {moeda(nota.bruto_ajustado)} ≠ {moeda(c.valor_bruto)}")
    if not liq_ok:
        partes.append(f"líquido {moeda(nota.valor_liquido)} ≠ {moeda(c.valor_liquido)}")
    if not imp_ok:
        partes.append(f"impostos {moeda(ret_sieg)} ≠ {moeda(c.total_retencoes)}")
    ident_ok = bruto_ok and liq_ok
    return True, ident_ok, (ident_ok and imp_ok), "; ".join(partes)


def _cmp_renew(nota, c):
    # O Renew guarda o valor de FACE / BRUTO da nota (= Valor_Servico), o valor
    # ANTES das retenções e ANTES do desconto — confirmado com dados reais do
    # cliente (38/38 notas com retenção casaram com o bruto, 0 com o líquido).
    # Por isso comparamos com `valor_servico` (bruto puro), NÃO com o ajustado do
    # desconto: o desconto só abate na frente do SPData (que o cliente lança
    # líquido do desconto), não aqui.
    data_ok = bool(nota.emissao and c.emissao and nota.emissao == c.emissao)
    valor_ok = valores_batem(nota.valor_servico, c.valor)
    partes = []
    if not data_ok:
        partes.append(f"data {_fmt_data(nota.emissao)} ≠ {_fmt_data(c.emissao)}")
    if not valor_ok:
        partes.append(f"valor {moeda(nota.valor_servico)} ≠ {moeda(c.valor)}")
    # a identidade do arquivo é o VALOR (o número já casou); a data é conferência.
    return data_ok, valor_ok, valor_ok, "; ".join(partes)


def _veredito(lanc, arq):
    if lanc.status == STATUS_FALTA or arq.status == STATUS_FALTA:
        return "pendente"
    if lanc.status == STATUS_OK and arq.status == STATUS_OK:
        return "gerenciada"
    return "ressalva"


def conciliar(autorizadas, canceladas, spdata, renew):
    idx_sp = _indexar_por_cnpj(spdata, lambda x: x.cnpj)
    idx_rn = _indexar_por_cnpj(renew, lambda x: x.cnpj_emissor)

    res = ResultadoConciliacao(canceladas=list(canceladas))
    for nota in autorizadas:
        lanc, lanc_row = _avaliar(nota, idx_sp.get(nota.cnpj_prestador, []), _cmp_spdata)
        arq, arq_row = _avaliar(nota, idx_rn.get(nota.cnpj_prestador, []), _cmp_renew)
        veredito = _veredito(lanc, arq)
        res.itens.append(ItemConciliacao(nota, lanc, arq, veredito, lanc_row, arq_row))

        if lanc.status == STATUS_FALTA:
            res.qt_falta_lancar += 1
        if arq.status == STATUS_FALTA:
            res.qt_falta_arquivar += 1
        if veredito == "gerenciada":
            res.qt_gerenciadas += 1
        elif veredito == "ressalva":
            res.qt_ressalva += 1

    res.total_universo = len(res.itens)
    res.valor_total = round(sum(i.nota.valor_servico for i in res.itens), 2)
    res.qt_canceladas = len(res.canceladas)

    # CON-02/03: confronto inverso — lançamentos do SP Data que NÃO constam do
    # SIEG (nem nas autorizadas, nem nas canceladas). "Consta" = mesmo CNPJ e
    # número (exato ou composto por sufixo); valor não importa aqui.
    idx_sieg = _indexar_por_cnpj(list(autorizadas) + list(canceladas),
                                 lambda n: n.cnpj_prestador)

    def _consta_no_sieg(sp):
        for n in idx_sieg.get(sp.cnpj, []):
            if n.numero_norm == sp.numero_norm or _casa_numero(sp.numero_norm, n.numero_norm):
                return True
        return False

    res.sp_sem_sieg = [sp for sp in spdata
                       if sp.numero_norm and not _consta_no_sieg(sp)]

    # CON-04: duplicidades no SP Data — mesmo CNPJ + número aparecendo >1 vez.
    grupos = {}
    for sp in spdata:
        if sp.numero_norm:
            grupos.setdefault((sp.cnpj, sp.numero_norm), []).append(sp)
    res.sp_duplicadas = [sp for g in grupos.values() if len(g) > 1 for sp in g]

    res.qt_sp_sem_sieg = len(res.sp_sem_sieg)
    res.qt_sp_duplicadas = len(res.sp_duplicadas)
    return res
