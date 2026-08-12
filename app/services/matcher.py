from dataclasses import dataclass, field
from app.services.normalizacao import valores_batem

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


@dataclass
class ResultadoConciliacao:
    itens: list = field(default_factory=list)
    canceladas: list = field(default_factory=list)
    total_universo: int = 0
    valor_total: float = 0.0
    qt_gerenciadas: int = 0
    qt_ressalva: int = 0
    qt_falta_lancar: int = 0
    qt_falta_arquivar: int = 0
    qt_canceladas: int = 0


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
    """`candidatos_cnpj` = itens do MESMO CNPJ do fornecedor. Casa por número:
    o número exato tem prioridade (aí valor/data são conferência → 🟢/🟡); se não
    houver número exato, tenta o número composto por sufixo, que só vale como a
    mesma nota quando o VALOR bate (guarda contra falso-positivo).
    `comparar(nota, cand) -> (data_ok, valores_ok, detalhe)`."""
    if not candidatos_cnpj:
        return Frente(STATUS_FALTA, "")

    exatos = [c for c in candidatos_cnpj
              if nota.numero_norm and c.numero_norm == nota.numero_norm]
    if exatos:
        melhor = None
        for c in exatos:
            data_ok, valores_ok, detalhe = comparar(nota, c)
            if data_ok and valores_ok:
                return Frente(STATUS_OK, "")
            acertos = int(data_ok) + int(valores_ok)
            if melhor is None or acertos > melhor[0]:
                melhor = (acertos, detalhe)
        return Frente(STATUS_DIVERG, melhor[1])

    for c in candidatos_cnpj:
        if _casa_numero(nota.numero_norm, c.numero_norm):
            _, valores_ok, _ = comparar(nota, c)
            if valores_ok:
                return Frente(STATUS_OK, "")
    return Frente(STATUS_FALTA, "")


def _cmp_spdata(nota, c):
    # A data do SpData é a de LANÇAMENTO (= coluna ENTRADA), não a de emissão da
    # NF, então NÃO comparamos data nesta frente — só os valores (bruto e
    # líquido). data_ok=True sempre: o veredito 🟢 sai quando os valores batem.
    bruto_ok = valores_batem(nota.valor_servico, c.valor_bruto)
    liq_ok = valores_batem(nota.valor_liquido, c.valor_liquido)
    partes = []
    if not bruto_ok:
        partes.append(f"bruto R$ {nota.valor_servico:.2f}≠R$ {c.valor_bruto:.2f}")
    if not liq_ok:
        partes.append(f"líquido R$ {nota.valor_liquido:.2f}≠R$ {c.valor_liquido:.2f}")
    return True, (bruto_ok and liq_ok), "; ".join(partes)


def _cmp_renew(nota, c):
    # O Renew guarda o valor de FACE (bruto) da nota, então comparamos com o
    # Valor_Servico do Sieg (bruto), não com o líquido. A data do Renew é a de
    # emissão de verdade, então aqui a data entra como conferência.
    data_ok = bool(nota.emissao and c.emissao and nota.emissao == c.emissao)
    valor_ok = valores_batem(nota.valor_servico, c.valor)
    partes = []
    if not data_ok:
        partes.append(f"data {_fmt_data(nota.emissao)}≠{_fmt_data(c.emissao)}")
    if not valor_ok:
        partes.append(f"valor R$ {nota.valor_servico:.2f}≠R$ {c.valor:.2f}")
    return data_ok, valor_ok, "; ".join(partes)


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
        lanc = _avaliar(nota, idx_sp.get(nota.cnpj_prestador, []), _cmp_spdata)
        arq = _avaliar(nota, idx_rn.get(nota.cnpj_prestador, []), _cmp_renew)
        veredito = _veredito(lanc, arq)
        res.itens.append(ItemConciliacao(nota, lanc, arq, veredito))

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
    return res
