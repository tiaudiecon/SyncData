from dataclasses import dataclass
from datetime import date
from app.services.normalizacao import so_digitos, normalizar_numero_nf, limpar_moeda, para_data
from app.services.planilha import abrir_planilha, mapa_cabecalho, indice, exigir_colunas


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
    iss: float = 0.0
    iss_retido: bool = False
    inss: float = 0.0
    ir: float = 0.0
    pis: float = 0.0
    cofins: float = 0.0
    csll: float = 0.0
    deducoes: float = 0.0
    desc_incondic: float = 0.0
    desc_condic: float = 0.0
    outret: float = 0.0
    aliquota: float = 0.0
    base_calculo: float = 0.0
    optante_sn: bool = False        # Optante_SN: 1=Simples Nacional, 2=normal

    @property
    def descontos(self) -> float:
        return round(self.deducoes + self.desc_incondic + self.desc_condic, 2)

    @property
    def bruto_ajustado(self) -> float:
        return round(self.valor_servico - self.descontos, 2)

    @property
    def total_retencoes(self) -> float:
        # Retenção REAL = Valor_Servico − Valor_Liquido (campo padrão da NFS-e: o
        # quanto o prestador deixou de receber). É o número confiável. Neste export
        # do Sieg as colunas individuais (IR/PIS/COFINS/CSLL) se sobrepõem ao
        # OutRetencoes; somá-las inflava o total (contava em dobro qdo OutRet≠0).
        return round(max(0.0, self.valor_servico - self.valor_liquido), 2)

    @property
    def csrf(self) -> float:
        # PIS/COFINS/CSLL não são confiáveis isolados neste export (o CSLL guarda o
        # CSRF cheio, 4,65%). Deriva do total real: CSRF = total − IRRF − INSS − (ISS
        # se retido). Assim ISS(se retido)+INSS+IRRF+CSRF fecha com o Total ret.
        iss = self.iss if self.iss_retido else 0.0
        return round(max(0.0, self.total_retencoes - self.ir - self.inss - iss), 2)


def _e_cancelada(dt_cancel, status) -> bool:
    if dt_cancel not in (None, "", "-"):
        return True
    return "cancel" in str(status or "").lower()


def _e_retido(v) -> bool:
    return str(v or "").strip().lower().startswith("s")


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
    # impostos (opcionais — se faltarem, ficam 0)
    i_ir = indice(mapa, "IR"); i_iss = indice(mapa, "ISS")
    i_issret = indice(mapa, "ISS_Retido"); i_csll = indice(mapa, "CSLL")
    i_pis = indice(mapa, "PIS"); i_cofins = indice(mapa, "COFINS")
    i_inss = indice(mapa, "INSS"); i_ded = indice(mapa, "Deducoes")
    i_di = indice(mapa, "Desconto_Incondic"); i_dc = indice(mapa, "Desconto_Condic")
    i_out = indice(mapa, "OutRetencoes"); i_aliq = indice(mapa, "Aliquota")
    i_base = indice(mapa, "Base_Calculo"); i_optsn = indice(mapa, "Optante_SN")

    exigir_colunas(
        {"Numero": i_num, "Dt_Emissao": i_emi, "Prestador": i_prest,
         "Tomador": i_tom, "Valor_Servico": i_serv, "Valor_Liquido": i_liq},
        lambda nome: (
            f"Planilha do Sieg inválida: não encontrei a coluna '{nome}'. "
            "Confira se o arquivo do Sieg (NFS-e) foi enviado no campo correto."
        ),
    )

    def val(row, i):
        return row[i] if (i is not None and i < len(row)) else None

    def moeda(row, i):
        return limpar_moeda(val(row, i))

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
            valor_servico=moeda(row, i_serv),
            valor_liquido=moeda(row, i_liq),
            cancelada=cancelada,
            iss=moeda(row, i_iss), iss_retido=_e_retido(val(row, i_issret)),
            inss=moeda(row, i_inss), ir=moeda(row, i_ir),
            pis=moeda(row, i_pis), cofins=moeda(row, i_cofins), csll=moeda(row, i_csll),
            deducoes=moeda(row, i_ded), desc_incondic=moeda(row, i_di),
            desc_condic=moeda(row, i_dc), outret=moeda(row, i_out),
            aliquota=moeda(row, i_aliq), base_calculo=moeda(row, i_base),
            optante_sn=(str(val(row, i_optsn) or "").strip() == "1"),
        )
        (canceladas if cancelada else autorizadas).append(nota)
    return autorizadas, canceladas
