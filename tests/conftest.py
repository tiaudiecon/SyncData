import os
import tempfile

# Aponta o SQLite para um arquivo temporário ANTES de qualquer import do app.
_DB = os.path.join(tempfile.mkdtemp(prefix="syncdata_test_"), "teste.db")
os.environ["SYNCDATA_DB"] = _DB

import pytest


@pytest.fixture()
def client():
    from app.main import app
    from app.database import Base, engine, SessionLocal
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    from fastapi.testclient import TestClient
    c = TestClient(app)
    yield c
    # limpa as tabelas entre os testes (mesmo banco, isolamento por linhas)
    from app.models import (Config, Conciliacao, ConciliacaoItem, TabelaAliquota,
                            ExcecaoFornecedor, ValidacaoImposto)
    db = SessionLocal()
    for modelo in (ConciliacaoItem, Conciliacao, Config, TabelaAliquota,
                   ExcecaoFornecedor, ValidacaoImposto):
        db.query(modelo).delete()
    db.commit()
    db.close()


@pytest.fixture()
def db_limpo():
    """Zera a tabela de alíquotas antes do teste (isolamento p/ REG-02)."""
    from app.database import Base, engine, SessionLocal
    from app import models  # noqa: F401
    from app.models import TabelaAliquota
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.query(TabelaAliquota).delete()
    db.commit()
    db.close()
    yield
