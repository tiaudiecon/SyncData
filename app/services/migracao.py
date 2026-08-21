"""Micro-migrações idempotentes de schema (SQLite).

O `Base.metadata.create_all` cria tabelas novas, mas NÃO altera tabelas que já
existem no banco do cliente. Para colunas novas em tabelas antigas usamos um
`ALTER TABLE ... ADD COLUMN` idempotente rodado no startup.
"""
from sqlalchemy import inspect, text

# (tabela, coluna, tipo_ddl)
_COLUNAS = [
    ("conciliacao", "competencia", "VARCHAR"),   # INI-02
    ("conciliacao", "periodo_inicio", "VARCHAR"),   # período da conferência (data início)
    ("conciliacao", "periodo_fim", "VARCHAR"),      # período da conferência (data fim)
    ("tabela_aliquota", "cbs", "FLOAT"),         # reforma tributária (prep)
    ("tabela_aliquota", "ibs", "FLOAT"),
]


def garantir_colunas(engine):
    insp = inspect(engine)
    tabelas = set(insp.get_table_names())
    existentes = {t: {c["name"] for c in insp.get_columns(t)} for t in tabelas}
    with engine.begin() as con:
        for tabela, coluna, tipo in _COLUNAS:
            if tabela in existentes and coluna not in existentes[tabela]:
                con.execute(text(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}"))
