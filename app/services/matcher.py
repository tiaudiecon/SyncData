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


def _indexar(itens, get_num, get_cnpj):
    idx = {}
    for it in itens:
        idx.setdefault((get_num(it), get_cnpj(it)), []).append(it)
    return idx


def _avaliar(nota, candidatos, comparar):
    """`comparar(nota, cand) -> (data_ok, valores_ok, detalhe)`. Retorna a
    melhor Frente da lista de candidatos (mesmo Nº+CNPJ)."""
    if not candidatos:
        return Frente(STATUS_FALTA, "")
    melhor = None
    for cand in candidatos:
        data_ok, valores_ok, detalhe = comparar(nota, cand)
        if data_ok and valores_ok:
            return Frente(STATUS_OK, "")
        acertos = int(data_ok) + int(valores_ok)
        if melhor is None or acertos > melhor[0]:
            melhor = (acertos, detalhe)
    return Frente(STATUS_DIVERG, melhor[1])


def _cmp_spdata(nota, c):
    data_ok = bool(nota.emissao and c.emissao and nota.emissao == c.emissao)
    bruto_ok = valores_batem(nota.valor_servico, c.valor_bruto)
    liq_ok = valores_batem(nota.valor_liquido, c.valor_liquido)
    partes = []
    if not data_ok:
        partes.append(f"data {_fmt_data(nota.emissao)}≠{_fmt_data(c.emissao)}")
    if not bruto_ok:
        partes.append(f"bruto R$ {nota.valor_servico:.2f}≠R$ {c.valor_bruto:.2f}")
    if not liq_ok:
        partes.append(f"líquido R$ {nota.valor_liquido:.2f}≠R$ {c.valor_liquido:.2f}")
    return data_ok, (bruto_ok and liq_ok), "; ".join(partes)


def _cmp_renew(nota, c):
    # O Renew guarda o valor de FACE (bruto) da nota, então comparamos com o
    # Valor_Servico do Sieg (bruto), não com o líquido.
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
    idx_sp = _indexar(spdata, lambda x: x.numero_norm, lambda x: x.cnpj)
    idx_rn = _indexar(renew, lambda x: x.numero_norm, lambda x: x.cnpj_emissor)

    res = ResultadoConciliacao(canceladas=list(canceladas))
    for nota in autorizadas:
        chave = (nota.numero_norm, nota.cnpj_prestador)
        lanc = _avaliar(nota, idx_sp.get(chave, []), _cmp_spdata)
        arq = _avaliar(nota, idx_rn.get(chave, []), _cmp_renew)
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
