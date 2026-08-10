import os
import sys
import time
import socket
import threading
import webbrowser
from pathlib import Path


def _diretorio_aplicacao():
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parent
    executavel = Path(sys.executable).resolve().parent
    candidato = executavel.parent.parent
    if (candidato / "templates").is_dir() and (candidato / "static").is_dir():
        return candidato
    return executavel


os.chdir(_diretorio_aplicacao())

import uvicorn
from app.main import app


def _abrir_navegador(port):
    alvo = "127.0.0.1"
    for _ in range(240):
        try:
            with socket.create_connection((alvo, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.25)
    else:
        return
    try:
        webbrowser.open(f"http://{alvo}:{port}")
    except Exception:
        pass


if __name__ == "__main__":
    host = os.getenv("SYNCDATA_HOST", "127.0.0.1")
    port = int(os.getenv("SYNCDATA_PORT", "8000"))
    if os.getenv("SYNCDATA_ABRIR_NAVEGADOR", "1") != "0":
        threading.Thread(target=_abrir_navegador, args=(port,), daemon=True).start()
    uvicorn.run(app, host=host, port=port)
