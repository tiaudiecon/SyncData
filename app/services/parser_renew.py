from dataclasses import dataclass
from datetime import date
from app.services.normalizacao import so_digitos, normalizar_numero_nf, limpar_moeda, para_data
from app.services.planilha import abrir_planilha, mapa_cabecalho, indice, exigir_colunas


@dataclass
class RegistroRenew:
    numero: str
    numero_norm: str
    cnpj_emissor: str
    fornecedor: str
    emissao: "date | None"
    valor: float          # `Valor da NF` = valor de FACE/BRUTO da nota


def ler_renew(arquivo):
    """Lê o Renew. `Valor da NF` é o valor de FACE (bruto) da nota — confirmado
    com dados reais do cliente (36/36 notas com retenção bateram com o bruto do
    Sieg, 0 com o líquido). Por isso o matcher compara este valor com o
    `Valor_Servico` (bruto) do Sieg, não com o líquido."""
    headers, linhas = abrir_planilha(arquivo)
    mapa = mapa_cabecalho(headers)

    i_num = indice(mapa, "Nº NF / Série", "No NF / Serie", "NF / Série")
    i_cnpj = indice(mapa, "CNPJ do Emissor")
    i_forn = indice(mapa, "Fornecedor Emitente")
    i_emi = indice(mapa, "Data de Emissão")
    i_val = indice(mapa, "Valor da NF")

    exigir_colunas(
        {"Nº NF / Série": i_num, "CNPJ do Emissor": i_cnpj,
         "Data de Emissão": i_emi, "Valor da NF": i_val},
        lambda nome: (
            f"Planilha do Renew inválida: não encontrei a coluna '{nome}'. "
            "Confira se o arquivo do Renew foi enviado no campo correto."
        ),
    )

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
            valor=limpar_moeda(val(row, i_val)),
        ))
    return itens
