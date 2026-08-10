from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import Base, engine
from app import models  # noqa: F401  (registra as tabelas no metadata)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SyncData")

import os
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
def health():
    return {"ok": True}
