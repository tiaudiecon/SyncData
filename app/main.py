import os
from urllib.parse import urlsplit
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
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
from app.routers import excecoes
from app.routers import validacoes
from app.routers import aceites

Base.metadata.create_all(bind=engine)
garantir_colunas(engine)   # INI-02: adiciona colunas novas em bancos antigos

# Semeia a tabela de alíquotas padrão (REG-02), idempotente.
_db = SessionLocal()
try:
    garantir_padrao(_db)
finally:
    _db.close()

app = FastAPI(title="SyncData")

# Hosts aceitos: só a própria máquina ("testserver" é o host do TestClient).
_HOSTS_LOCAIS = {"localhost", "127.0.0.1", "testserver"}
_METODOS_ESCRITA = {"POST", "PUT", "DELETE", "PATCH"}


@app.middleware("http")
async def guarda_origem(request, call_next):
    """App local e sem login: qualquer página aberta no navegador do operador
    alcança o 127.0.0.1. Duas travas baratas, sem dependência nova:

    - `Host`: barra DNS rebinding (site que resolve o próprio domínio para
      127.0.0.1 vira "mesma origem" e leria o histórico/dados.json do cliente);
    - `Origin` nos métodos de escrita: barra CSRF (um POST de outra aba trocando
      o CNPJ do cliente ou marcando divergência como aceita).

    Requisição SEM `Origin` passa de propósito: é o caso da própria janela
    (webview/Edge --app, mesma origem) e de chamadas locais tipo curl.
    """
    host = urlsplit("//" + (request.headers.get("host") or "")).hostname
    if host not in _HOSTS_LOCAIS:
        return PlainTextResponse("Host não permitido", status_code=403)
    if request.method in _METODOS_ESCRITA:
        origem = request.headers.get("origin")
        if origem and urlsplit(origem).hostname not in _HOSTS_LOCAIS:
            return PlainTextResponse("Origem não permitida", status_code=403)
    return await call_next(request)


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
app.include_router(excecoes.router)
app.include_router(validacoes.router)
app.include_router(aceites.router)


@app.get("/health")
def health():
    """Devolve o token do boot (posto no ambiente pelo `run.py`) para o
    lançador confirmar que quem respondeu na porta é ESTE servidor, e não outro
    processo que já estivesse escutando ali."""
    return {"ok": True, "token": os.getenv("SYNCDATA_BOOT_TOKEN", "")}
