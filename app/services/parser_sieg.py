from dataclasses import dataclass
from datetime import date
from app.services.normalizacao import so_digitos, normalizar_numero_nf, limpar_moeda, para_data
from app.services.planilha import abrir_planilha, mapa_cabecalho, indice


@dataclass
class NotaSieg:
    numero: str
    numero_norm: str
    cnpj_prestador: str
    nome_prestador: str
    emissao: "date | None"
    valor_servico: float
    valor_liquido: float
    cancelada: bool


def _e_cancelada(dt_cancel, status) -> bool:
    if dt_cancel not in (None, "", "-"):
        return True
    return "cancel" in str(status or "").lower()


def ler_sieg(arquivo, cnpj_cliente: str):
    """Lê o Sieg NFS-e. Mantém só linhas onde Tomador == cnpj_cliente.
    Retorna (autorizadas, canceladas)."""
    alvo = so_digitos(cnpj_cliente)
    headers, linhas = abrir_planilha(arquivo)
    mapa = mapa_cabecalho(headers)

    i_num = indice(mapa, "Numero")
    i_emi = indice(mapa, "Dt_Emissao")
    i_prest = indice(mapa, "Prestador")
    i_nome = indice(mapa, "RzPrestador")
    i_tom = indice(mapa, "Tomador")
    i_serv = indice(mapa, "Valor_Servico")
    i_liq = indice(mapa, "Valor_Liquido")
    i_cancel = indice(mapa, "Dt_Cancelamento")
    i_status = indice(mapa, "Status")

    def val(row, i):
        return row[i] if (i is not None and i < len(row)) else None

    autorizadas, canceladas = [], []
    for row in linhas:
        if not row:
            continue
        if so_digitos(val(row, i_tom)) != alvo:
            continue
        numero = str(val(row, i_num) or "").strip()
        cancelada = _e_cancelada(val(row, i_cancel), val(row, i_status))
        nota = NotaSieg(
            numero=numero,
            numero_norm=normalizar_numero_nf(numero),
            cnpj_prestador=so_digitos(val(row, i_prest)),
            nome_prestador=str(val(row, i_nome) or "").strip(),
            emissao=para_data(val(row, i_emi)),
            valor_servico=limpar_moeda(val(row, i_serv)),
            valor_liquido=limpar_moeda(val(row, i_liq)),
            cancelada=cancelada,
        )
        (canceladas if cancelada else autorizadas).append(nota)
    return autorizadas, canceladas
