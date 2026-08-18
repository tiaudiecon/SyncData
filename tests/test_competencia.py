"""INI-02: cadastro de competência (mês/ano) e organização do histórico."""
import re
from sqlalchemy import create_engine, inspect, text
from app.services.tempo import formatar_competencia
from app.services.migracao import garantir_colunas
from app.routers.conciliar import _RX_COMPETENCIA


def test_formatar_competencia():
    assert formatar_competencia("2026-08") == "ago/2026"
    assert formatar_competencia("2026-01") == "jan/2026"
    assert formatar_competencia("") == ""
    assert formatar_competencia(None) == ""
    assert formatar_competencia("lixo") == ""


def test_regex_competencia_aceita_so_aaaa_mm_valido():
    assert _RX_COMPETENCIA.match("2026-08")
    assert _RX_COMPETENCIA.match("2026-12")
    assert not _RX_COMPETENCIA.match("2026-13")   # mês inválido
    assert not _RX_COMPETENCIA.match("2026-00")
    assert not _RX_COMPETENCIA.match("08/2026")
    assert not _RX_COMPETENCIA.match("")


def test_migracao_adiciona_competencia_em_banco_antigo(tmp_path):
    # Simula um banco antigo (tabela conciliacao SEM a coluna competencia).
    eng = create_engine(f"sqlite:///{tmp_path/'antigo.db'}")
    with eng.begin() as con:
        con.execute(text("CREATE TABLE conciliacao (id INTEGER PRIMARY KEY, cnpj VARCHAR)"))
    garantir_colunas(eng)
    cols = {c["name"] for c in inspect(eng).get_columns("conciliacao")}
    assert "competencia" in cols
    # idempotente: rodar de novo não quebra
    garantir_colunas(eng)
