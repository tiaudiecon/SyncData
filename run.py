import os
import sys
import time
import shutil
import socket
import tempfile
import threading
import subprocess
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


def _rodar_servidor(host, port):
    """Roda o uvicorn numa thread. `install_signal_handlers` é neutralizado
    porque só funciona na thread principal (aqui a principal fica com a janela)."""
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    servidor = uvicorn.Server(config)
    servidor.install_signal_handlers = lambda: None
    servidor.run()


def _esperar_porta(host, port, tentativas=240):
    for _ in range(tentativas):
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


# Edge/Chrome em "modo app" (--app): janela própria, sem abas nem barra de
# endereço. Com um --user-data-dir dedicado, o processo do navegador vive só
# por essa janela — quando o usuário fecha, o processo termina e nós encerramos
# o servidor. É o que dá o comportamento de "aplicativo" sem runtime extra.
_NAVEGADORES = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
]


def _localizar_navegador():
    for candidato in _NAVEGADORES:
        caminho = os.path.expandvars(candidato)
        if os.path.exists(caminho):
            return caminho
    return None


def _abrir_janela_app(url):
    """Abre a janela do app. Devolve (processo, pasta_perfil) ou None."""
    navegador = _localizar_navegador()
    if not navegador:
        return None
    perfil = tempfile.mkdtemp(prefix="syncdata_app_")
    try:
        proc = subprocess.Popen([
            navegador, "--app=" + url, "--user-data-dir=" + perfil,
            "--window-size=1360,860", "--no-first-run", "--no-default-browser-check",
        ])
    except Exception:
        shutil.rmtree(perfil, ignore_errors=True)
        return None
    return proc, perfil


_TITULO = "Conciliação de Fornecedores — SyncData"


def _janela_pywebview(url):
    """Janela NATIVA via pywebview (WebView2). Bloqueia até o usuário fechar.
    Devolve True se abriu/rodou; False se o backend não está disponível (aí
    caímos no Edge/Chrome --app)."""
    try:
        import webview
        webview.create_window(_TITULO, url, width=1360, height=860)
        webview.start()              # bloqueia até a janela fechar
        return True
    except Exception:
        print("[janela] pywebview indisponível, usando navegador em modo app", flush=True)
        return False


if __name__ == "__main__":
    host = os.getenv("SYNCDATA_HOST", "127.0.0.1")
    port = int(os.getenv("SYNCDATA_PORT", "8000"))
    abrir_janela = os.getenv("SYNCDATA_ABRIR_NAVEGADOR", "1") != "0"

    threading.Thread(target=_rodar_servidor, args=(host, port), daemon=True).start()
    if not _esperar_porta(host, port):
        sys.exit(1)

    url = f"http://{host}:{port}"

    # 1) Janela nativa (pywebview/WebView2) — o ideal.
    if abrir_janela and _janela_pywebview(url):
        os._exit(0)

    # 2) Fallback: Edge/Chrome em modo --app (janela dedicada).
    janela = _abrir_janela_app(url) if abrir_janela else None
    if janela:
        processo, perfil = janela
        try:
            processo.wait()          # bloqueia até a JANELA do app ser fechada
        finally:
            shutil.rmtree(perfil, ignore_errors=True)
        os._exit(0)                  # encerra o processo inteiro (servidor na thread daemon)
    else:
        # 3) Último recurso: navegador padrão; mantém o servidor no ar.
        if abrir_janela:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        while True:
            time.sleep(3600)
