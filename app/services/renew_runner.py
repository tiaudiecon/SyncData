import os
import sys
import time
import subprocess
from pathlib import Path

RELATORIO_NOME = "Relatório Renew.xlsx"
_EXE_PADRAO = "Renew_10.4.exe"


def localizar_renew_dir() -> Path:
    """Pasta do Renew (exe + poppler/tesseract/clientes.txt). Prioridade:
    env SYNCDATA_RENEW_DIR; congelado -> <_MEIPASS>/renew."""
    env = os.getenv("SYNCDATA_RENEW_DIR")
    if env:
        return Path(env)
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "renew"
    raise RuntimeError("Renew não localizado: defina SYNCDATA_RENEW_DIR.")


def localizar_renew_exe() -> Path:
    return localizar_renew_dir() / os.getenv("SYNCDATA_RENEW_EXE", _EXE_PADRAO)


def _pdfs(pasta):
    return [f for f in Path(pasta).iterdir()
            if f.is_file() and f.suffix.lower() == ".pdf"]


def contar_pdfs(pasta) -> int:
    return len(_pdfs(pasta))


def contar_renomeados(pasta) -> int:
    """PDFs já renomeados pelo Renew (prefixo 'E_'). Sinal de progresso."""
    return sum(1 for f in _pdfs(pasta) if f.name.startswith("E_"))


def rodar_renew(pasta, comando=None, cwd=None, on_progress=None, intervalo=1.0) -> Path:
    """Roda o Renew na pasta (CLI) e devolve o caminho do 'Relatório Renew.xlsx'.
    Acompanha o progresso contando os PDFs já renomeados. Levanta RuntimeError se
    o Renew terminar com código != 0 ou não gerar o relatório."""
    pasta = Path(pasta)
    if comando is None:
        exe = localizar_renew_exe()
        comando = [str(exe)]
        cwd = cwd or str(exe.parent)
    proc = subprocess.Popen([*comando, str(pasta)], cwd=cwd,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while proc.poll() is None:
        if on_progress:
            on_progress(contar_renomeados(pasta), contar_pdfs(pasta))
        time.sleep(intervalo)
    saida = proc.stdout.read() if proc.stdout else ""
    if proc.returncode != 0:
        cauda = "\n".join(saida.splitlines()[-8:])
        raise RuntimeError(f"O Renew falhou (código {proc.returncode}).\n{cauda}")
    total = contar_pdfs(pasta)
    if on_progress:
        on_progress(total, total)
    rel = pasta / RELATORIO_NOME
    if not rel.is_file():
        raise RuntimeError("O Renew rodou mas não gerou o 'Relatório Renew.xlsx'.")
    return rel
