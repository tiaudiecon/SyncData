from dataclasses import dataclass
from datetime import date
from app.services.normalizacao import (
    so_digitos, normalizar_numero_nf, limpar_moeda, para_data,
)


@dataclass
class LancamentoSpData:
    numero: str
    numero_norm: str
    cnpj: str
    fornecedor: str
    emissao: "date | None"
    valor_bruto: float
    valor_liquido: float


def ler_spdata(conteudo: bytes) -> "list[LancamentoSpData]":
    """Lê o .txt do SpData (pipe-delimited, Latin-1). Mapeia por NOME de
    coluna no cabeçalho — robusto a mudança de ordem."""
    texto = conteudo.decode("cp1252", errors="replace")
    linhas = [ln for ln in texto.splitlines() if ln.strip()]
    if not linhas:
        return []

    cabecalho = [c.strip().upper() for c in linhas[0].split("|")]
    idx = {nome: i for i, nome in enumerate(cabecalho)}

    def celula(campos, nome):
        i = idx.get(nome)
        return campos[i].strip() if i is not None and i < len(campos) else ""

    itens = []
    for linha in linhas[1:]:
        campos = linha.split("|")
        numero = celula(campos, "NOTA")
        itens.append(LancamentoSpData(
            numero=numero,
            numero_norm=normalizar_numero_nf(numero),
            cnpj=so_digitos(celula(campos, "CNPJ_CPF")),
            fornecedor=celula(campos, "FORNECEDOR"),
            emissao=para_data(celula(campos, "EMISSAO")),
            valor_bruto=limpar_moeda(celula(campos, "VALOR_BRUTO")),
            valor_liquido=limpar_moeda(celula(campos, "VALOR_LIQUIDO")),
        ))
    return itens
