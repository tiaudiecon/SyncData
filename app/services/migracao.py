"""Micro-migrações idempotentes de schema (SQLite).

O `Base.metadata.create_all` cria tabelas novas, mas NÃO altera tabelas que já
existem no banco do cliente. As colunas faltantes são derivadas DO PRÓPRIO
metadata dos modelos — nada de lista mantida à mão: esquecer de registrar uma
coluna nova deixaria o banco do cliente sem ela e o app quebraria em toda tela
com "no such column", sem o cliente ter como diagnosticar nem reverter.

Para cada tabela que JÁ existe no banco, comparamos as colunas do modelo com as
reais e emitimos `ALTER TABLE ... ADD COLUMN` para o que faltar. Limite
deliberado: o ADD COLUMN só admite coluna anulável e sem default — que é
exatamente o desenho de todas as colunas novas deste projeto. Renomear, remover
ou trocar tipo de coluna continua exigindo migração manual.
"""
from sqlalchemy import inspect, text


def garantir_colunas(engine):
    # Import tardio: `app.main` importa este módulo junto com o banco/modelos;
    # importar no topo criaria ciclo. O import de `models` é o que registra as
    # tabelas no metadata do Base.
    from app.database import Base
    from app import models  # noqa: F401

    insp = inspect(engine)
    existentes = {t: {c["name"] for c in insp.get_columns(t)}
                  for t in insp.get_table_names()}
    citar = engine.dialect.identifier_preparer.quote
    with engine.begin() as con:
        for nome, tabela in Base.metadata.tables.items():
            if nome not in existentes:
                continue                      # tabela nova: quem cria é o create_all
            for col in tabela.columns:
                if col.name in existentes[nome]:
                    continue
                tipo = col.type.compile(engine.dialect)
                con.execute(text(
                    f"ALTER TABLE {citar(nome)} ADD COLUMN {citar(col.name)} {tipo}"))
