from dataclasses import dataclass
from datetime import date
from app.services.normalizacao import so_digitos, normalizar_numero_nf, limpar_moeda, para_data
from app.services.planilha import abrir_planilha, mapa_cabecalho, indice


@dataclass
class RegistroRenew:
    numero: str
    numero_norm: str
    cnpj_emissor: str
    fornecedor: str
    emissao: "date | None"
    valor_liquido: float


def ler_renew(arquivo):
    """Lê o Renew. `Valor da NF` é tratado como valor LÍQUIDO."""
    headers, linhas = abrir_planilha(arquivo)
    mapa = mapa_cabecalho(headers)

    i_num = indice(mapa, "Nº NF / Série", "No NF / Serie", "NF / Série")
    i_cnpj = indice(mapa, "CNPJ do Emissor")
    i_forn = indice(mapa, "Fornecedor Emitente")
    i_emi = indice(mapa, "Data de Emissão")
    i_val = indice(mapa, "Valor da NF")

    def val(row, i):
        return row[i] if (i is not None and i < len(row)) else None

    itens = []
    for row in linhas:
        if not row:
            continue
        numero = str(val(row, i_num) or "").strip()
        if not numero:
            continue
        itens.append(RegistroRenew(
            numero=numero,
            numero_norm=normalizar_numero_nf(numero),
            cnpj_emissor=so_digitos(val(row, i_cnpj)),
            fornecedor=str(val(row, i_forn) or "").strip(),
            emissao=para_data(val(row, i_emi)),
            valor_liquido=limpar_moeda(val(row, i_val)),
        ))
    return itens
