import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine, SessionLocal
from app import models  # noqa: F401
from app.services.aliquotas import garantir_padrao
from app.services.migracao import garantir_colunas
from app.routers import setup
from app.routers import conciliar
from app.routers import resultado
from app.routers import historico, configuracoes
from app.routers import impostos
from app.routers import processar
from app.routers import pdf

Base.metadata.create_all(bind=engine)
garantir_colunas(engine)   # INI-02: adiciona colunas novas em bancos antigos

# Semeia a tabela de alíquotas padrão (REG-02), idempotente.
_db = SessionLocal()
try:
    garantir_padrao(_db)
finally:
    _db.close()

app = FastAPI(title="SyncData")

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(setup.router)
app.include_router(conciliar.router)
app.include_router(resultado.router)
app.include_router(historico.router)
app.include_router(configuracoes.router)
app.include_router(impostos.router)
app.include_router(processar.router)
app.include_router(pdf.router)


@app.get("/health")
def health():
    return {"ok": True}
