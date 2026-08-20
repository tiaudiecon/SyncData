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
    issqn: float = 0.0
    inss_pj: float = 0.0
    inss_auton: float = 0.0
    irpj: float = 0.0
    ir_auton: float = 0.0
    ir_coop: float = 0.0
    csrf: float = 0.0

    @property
    def inss(self) -> float:
        return round(self.inss_pj + self.inss_auton, 2)

    @property
    def ir(self) -> float:
        return round(self.irpj + self.ir_auton + self.ir_coop, 2)

    @property
    def total_retencoes(self) -> float:
        return round(self.issqn + self.inss + self.ir + self.csrf, 2)

    @property
    def valor_liquido(self) -> float:
        # Líquido do SP Data = Valor Bruto − Impostos (retenções). NÃO usa a coluna
        # VALOR_LIQUIDO do arquivo (que pode vir calculada de outra forma).
        return round(self.valor_bruto - self.total_retencoes, 2)


def ler_spdata(conteudo: bytes) -> "list[LancamentoSpData]":
    """Lê o .txt do SpData (pipe-delimited, Latin-1). Mapeia por NOME de
    coluna no cabeçalho — robusto a mudança de ordem."""
    texto = conteudo.decode("cp1252", errors="replace")
    linhas = [ln for ln in texto.splitlines() if ln.strip()]
    if not linhas:
        return []

    cabecalho = [c.strip().upper() for c in linhas[0].split("|")]
    idx = {nome: i for i, nome in enumerate(cabecalho)}

    for nome in ("NOTA", "CNPJ_CPF", "EMISSAO", "VALOR_BRUTO", "VALOR_LIQUIDO"):
        if nome not in idx:
            raise ValueError(
                f"Arquivo do SpData inválido: não encontrei a coluna '{nome}'. "
                "Confira se o arquivo do SpData foi enviado no campo correto."
            )

    def celula(campos, nome):
        i = idx.get(nome)
        return campos[i].strip() if i is not None and i < len(campos) else ""

    def moeda(campos, nome):
        return limpar_moeda(celula(campos, nome))

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
            valor_bruto=moeda(campos, "VALOR_BRUTO"),
            issqn=moeda(campos, "ISSQN"),
            inss_pj=moeda(campos, "INSS_PJ"), inss_auton=moeda(campos, "INSS_AUTON"),
            irpj=moeda(campos, "IRPJ"), ir_auton=moeda(campos, "IR_AUTON"),
            ir_coop=moeda(campos, "IR_COOP"), csrf=moeda(campos, "CSRF"),
        ))
    return itens
