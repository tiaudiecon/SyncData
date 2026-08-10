import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine
from app import models  # noqa: F401
from app.routers import setup
from app.routers import conciliar
from app.routers import resultado

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SyncData")

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(setup.router)
app.include_router(conciliar.router)
app.include_router(resultado.router)


@app.get("/health")
def health():
    return {"ok": True}
