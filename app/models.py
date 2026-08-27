from datetime import datetime, timezone
from sqlalchemy import (Boolean, Column, DateTime, Float, ForeignKey, Integer,
                        String, UniqueConstraint)
from sqlalchemy.orm import relationship
from app.database import Base


class Config(Base):
    """Configuração única do app (uma linha só). Guarda o CNPJ do cliente."""
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    cnpj_cliente = Column(String, nullable=False, default="")
    razao_social = Column(String, nullable=True)
    configurado = Column(Boolean, nullable=False, default=False)


class Conciliacao(Base):
    """Uma execução da conciliação (cabeçalho + totais)."""
    __tablename__ = "conciliacao"
    id = Column(Integer, primary_key=True)
    data_hora = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    competencia = Column(String, nullable=True, index=True)   # INI-02: "aaaa-mm"
    periodo_inicio = Column(String, nullable=True)   # data início da conferência ("aaaa-mm-dd")
    periodo_fim = Column(String, nullable=True)      # data fim da conferência ("aaaa-mm-dd")
    cnpj = Column(String, nullable=False)
    arquivo_spdata_nome = Column(String, nullable=True)
    arquivo_sieg_nome = Column(String, nullable=True)
    arquivo_renew_nome = Column(String, nullable=True)
    total_universo = Column(Integer, default=0)
    valor_total = Column(Float, default=0.0)
    qt_gerenciadas = Column(Integer, default=0)
    qt_ressalva = Column(Integer, default=0)
    qt_falta_lancar = Column(Integer, default=0)
    qt_falta_arquivar = Column(Integer, default=0)
    qt_canceladas = Column(Integer, default=0)
    pasta_pdfs = Column(String, nullable=True)

    itens = relationship("ConciliacaoItem", back_populates="conciliacao",
                         cascade="all, delete-orphan")


class ConciliacaoItem(Base):
    """Uma nota do Sieg dentro de uma conciliação (as 2 frentes)."""
    __tablename__ = "conciliacao_item"
    id = Column(Integer, primary_key=True)
    conciliacao_id = Column(Integer, ForeignKey("conciliacao.id"), nullable=False, index=True)
    numero = Column(String, nullable=True)
    cnpj_fornecedor = Column(String, nullable=True)
    nome_fornecedor = Column(String, nullable=True)
    data_emissao = Column(String, nullable=True)     # "dd/mm/aaaa" (texto, já formatado)
    valor_bruto = Column(Float, default=0.0)
    valor_liquido = Column(Float, default=0.0)
    status_lancamento = Column(String, default="falta")   # ok|diverg|falta
    status_arquivo = Column(String, default="falta")      # ok|diverg|falta
    detalhe_lancamento = Column(String, default="")
    detalhe_arquivo = Column(String, default="")
    veredito = Column(String, default="pendente")         # gerenciada|ressalva|pendente
    cancelada = Column(Boolean, default=False)
    sp_valor_bruto = Column(Float, nullable=True)
    sp_valor_liquido = Column(Float, nullable=True)
    imp_sieg = Column(Float, default=0.0)
    imp_spdata = Column(Float, nullable=True)
    tem_desconto = Column(Boolean, default=False)
    impostos_json = Column(String, default="")
    arquivo_pdf = Column(String, nullable=True)

    conciliacao = relationship("Conciliacao", back_populates="itens")


class TabelaAliquota(Base):
    """Alíquotas base de retenção (REG-02), parametrizáveis com vigência por
    período. A tabela vigente p/ uma nota é a de maior `vigencia_inicio` ≤ data.
    Consolidado PIS/COFINS/CSLL (cód 5952) = pis + cofins + csll (derivado)."""
    __tablename__ = "tabela_aliquota"
    id = Column(Integer, primary_key=True)
    vigencia_inicio = Column(String, nullable=False)   # "aaaa-mm-dd"
    irpj = Column(Float, default=1.50)                 # % (cód 1708)
    pis = Column(Float, default=0.65)
    cofins = Column(Float, default=3.00)
    csll = Column(Float, default=1.00)
    # Reforma tributária — ainda NÃO efetivado; deixado preparado (default 0).
    cbs = Column(Float, default=0.0)
    ibs = Column(Float, default=0.0)


class ExcecaoFornecedor(Base):
    """Fornecedor marcado como EXCEÇÃO da regra de recálculo: a divergência de
    impostos é esperada (grupo dispensado de recolhimento). Vale por CNPJ, para
    TODAS as conciliações — inclusive as futuras (o operador não refaz sempre)."""
    __tablename__ = "excecao_fornecedor"
    id = Column(Integer, primary_key=True)
    cnpj = Column(String, nullable=False, unique=True, index=True)   # só dígitos
    nome = Column(String, nullable=True)
    observacao = Column(String, nullable=False, default="")
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    atualizado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


class ValidacaoImposto(Base):
    """Nota marcada manualmente como VALIDADA na divergência de impostos: o
    operador confirma que aquela nota NÃO tem erro de imposto. Diferente da
    exceção, vale APENAS para a competência trabalhada (não replica p/ as
    demais) — por isso a chave é competência + CNPJ + número da nota."""
    __tablename__ = "validacao_imposto"
    __table_args__ = (UniqueConstraint("competencia", "cnpj", "numero",
                                       name="uq_validacao_comp_cnpj_num"),)
    id = Column(Integer, primary_key=True)
    competencia = Column(String, nullable=False, index=True)   # "aaaa-mm"
    cnpj = Column(String, nullable=False)      # só dígitos
    numero = Column(String, nullable=False)    # só dígitos (número da nota)
    nome = Column(String, nullable=True)
    observacao = Column(String, nullable=False, default="")
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AceiteDivergencia(Base):
    """Divergência de VALOR (Sieg×SPData) ou de ARQUIVO aceita manualmente: o
    operador confirma que a nota está correta apesar de não bater (veredito
    ressalva/pendente), com justificativa. Vale SÓ para a competência — chave
    competência+CNPJ+número (como a ValidacaoImposto). Ortogonal ao imposto:
    limpa o erro de lançamento/arquivo, não o de imposto."""
    __tablename__ = "aceite_divergencia"
    __table_args__ = (UniqueConstraint("competencia", "cnpj", "numero",
                                       name="uq_aceite_comp_cnpj_num"),)
    id = Column(Integer, primary_key=True)
    competencia = Column(String, nullable=False, index=True)   # "aaaa-mm"
    cnpj = Column(String, nullable=False)      # só dígitos
    numero = Column(String, nullable=False)    # só dígitos (número da nota)
    nome = Column(String, nullable=True)
    observacao = Column(String, nullable=False, default="")
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
