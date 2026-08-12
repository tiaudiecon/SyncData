from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
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

    conciliacao = relationship("Conciliacao", back_populates="itens")
