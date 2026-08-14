import os
import sys
import time
import socket
import threading
import webbrowser
from pathlib import Path


def _diretorio_aplicacao():
    """No .exe (onedir), os dados empacotados (templates/static) ficam em
    `sys._MEIPASS` — a pasta `_internal` ao lado do executável. Trabalhamos a
    partir dali para o Jinja/StaticFiles acharem `templates/` e `static/`. Já o
    BANCO deve viver AO LADO do .exe (não dentro de `_internal`, que some numa
    reinstalação), então fixamos `SYNCDATA_DB` na pasta do executável.
    Em desenvolvimento, tudo roda a partir da raiz do projeto."""
    if getattr(sys, "frozen", False):
        pasta_exe = Path(sys.executable).resolve().parent
        os.environ.setdefault("SYNCDATA_DB", str(pasta_exe / "syncdata.db"))
        # App empacotado SEM console (windowed): o Windows deixa sys.stdout/stderr
        # como None, e uvicorn/print quebrariam ao escrever. Redireciona pra um log
        # ao lado do .exe (também serve pra depurar sem a janela preta).
        if sys.stdout is None or sys.stderr is None:
            try:
                _log = open(pasta_exe / "syncdata.log", "a", encoding="utf-8", buffering=1)
                if sys.stdout is None:
                    sys.stdout = _log
                if sys.stderr is None:
                    sys.stderr = _log
            except Exception:
                pass
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


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
