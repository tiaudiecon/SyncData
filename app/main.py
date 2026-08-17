import os
import sys
import time
import threading
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine
from app import models  # noqa: F401
from app.routers import setup
from app.routers import conciliar
from app.routers import resultado
from app.routers import historico, configuracoes
from app.routers import impostos
from app.routers import processar
from app.routers import pdf

Base.metadata.create_all(bind=engine)

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


# ---- Auto-encerramento quando o navegador fecha -----------------------------
# O app é um servidor local: fechar o navegador NÃO encerra o processo sozinho.
# A página manda um "keepalive" a cada 10s (ver base.html); se os sinais param
# (navegador/aba fechados) por mais que o timeout, o vigia encerra o .exe — assim
# não fica processo órfão no Gerenciador de Tarefas.
_ULTIMO_CONTATO = time.monotonic()


@app.get("/keepalive")
def keepalive():
    global _ULTIMO_CONTATO
    _ULTIMO_CONTATO = time.monotonic()
    return {"ok": True}


def _vigia_navegador(timeout_s: float):
    intervalo = max(2.0, min(10.0, timeout_s / 3))
    while True:
        time.sleep(intervalo)
        if time.monotonic() - _ULTIMO_CONTATO > timeout_s:
            os._exit(0)   # encerra o processo inteiro (uvicorn + threads)


# Só no .exe (frozen) ou com SYNCDATA_VIGIA=1 — nunca no dev/testes.
if getattr(sys, "frozen", False) or os.getenv("SYNCDATA_VIGIA") == "1":
    _timeout = float(os.getenv("SYNCDATA_VIGIA_TIMEOUT", "45"))
    threading.Thread(target=_vigia_navegador, args=(_timeout,), daemon=True).start()
