"""A micro-migração é derivada do metadata dos modelos — banco antigo, sem uma
coluna que o modelo já tem, precisa ganhar a coluna no startup (senão toda tela
quebra com 'no such column')."""
from sqlalchemy import create_engine, inspect, text
from app.services.migracao import garantir_colunas


def _colunas(engine, tabela):
    return {c["name"] for c in inspect(engine).get_columns(tabela)}


def test_adiciona_coluna_faltante_em_tabela_antiga(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'antigo.db'}")
    # schema "antigo": tabela_aliquota sem pis/cofins/csll/cbs/ibs
    with engine.begin() as con:
        con.execute(text("CREATE TABLE tabela_aliquota ("
                         "id INTEGER NOT NULL PRIMARY KEY, "
                         "vigencia_inicio VARCHAR NOT NULL, irpj FLOAT)"))
    assert "cbs" not in _colunas(engine, "tabela_aliquota")

    garantir_colunas(engine)

    cols = _colunas(engine, "tabela_aliquota")
    assert {"pis", "cofins", "csll", "cbs", "ibs"} <= cols
    garantir_colunas(engine)                       # idempotente
    assert _colunas(engine, "tabela_aliquota") == cols
    engine.dispose()


def test_nao_cria_tabela_que_nao_existe(tmp_path):
    """Tabela nova é assunto do create_all; a migração só ALTERA existentes."""
    engine = create_engine(f"sqlite:///{tmp_path / 'vazio.db'}")
    with engine.begin() as con:
        con.execute(text("CREATE TABLE config (id INTEGER NOT NULL PRIMARY KEY)"))
    garantir_colunas(engine)
    tabelas = set(inspect(engine).get_table_names())
    assert tabelas == {"config"}
    assert {"cnpj_cliente", "razao_social", "configurado"} <= _colunas(engine, "config")
    engine.dispose()
