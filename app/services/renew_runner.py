import os
import sys
import time
import tempfile
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


def _limite_segundos() -> float:
    """Teto de execução do Renew (env SYNCDATA_RENEW_TIMEOUT, em segundos)."""
    try:
        return float(os.getenv("SYNCDATA_RENEW_TIMEOUT", "1800"))
    except ValueError:
        return 1800.0


def rodar_renew(pasta, comando=None, cwd=None, on_progress=None, intervalo=1.0) -> Path:
    """Roda o Renew na pasta (CLI) e devolve o caminho do 'Relatório Renew.xlsx'.
    Acompanha o progresso contando os PDFs já renomeados. Levanta RuntimeError se
    o Renew terminar com código != 0, estourar o tempo limite ou não gerar o
    relatório.

    O teto de tempo existe porque o Renew roda com CREATE_NO_WINDOW: um diálogo
    modal invisível (ou um laço de OCR num PDF corrompido) travaria o laço para
    sempre, com a tela de progresso congelada e sem botão de cancelar."""
    pasta = Path(pasta)
    if comando is None:
        exe = localizar_renew_exe()
        comando = [str(exe)]
        cwd = cwd or str(exe.parent)
    limite = _limite_segundos()
    with tempfile.TemporaryFile("w+b") as logf:
        proc = subprocess.Popen([*comando, str(pasta)], cwd=cwd,
                                stdout=logf, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        inicio = time.monotonic()
        while proc.poll() is None:
            if on_progress:
                on_progress(contar_renomeados(pasta), contar_pdfs(pasta))
            if time.monotonic() - inicio > limite:
                proc.kill()                      # não deixa processo órfão segurando a pasta
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
                raise RuntimeError(
                    f"Renew excedeu o tempo limite ({limite:g} s) — verifique os PDFs "
                    "ou aumente SYNCDATA_RENEW_TIMEOUT.")
            time.sleep(intervalo)
        logf.seek(0)
        saida = logf.read().decode("utf-8", errors="replace")
    if proc.returncode != 0:
        cauda = "\n".join(saida.splitlines()[-8:])
        raise RuntimeError(f"O Renew falhou (código {proc.returncode}).\n{cauda}")
    if on_progress:
        total = contar_pdfs(pasta)
        on_progress(total, total)
    rel = pasta / RELATORIO_NOME
    if not rel.is_file():
        raise RuntimeError("O Renew rodou mas não gerou o 'Relatório Renew.xlsx'.")
    return rel


def processar_pasta(job_id, pasta, autorizadas, canceladas, lancamentos, cnpj,
                    nomes=None, runner=None):
    """Roda o Renew na pasta, concilia e salva. Atualiza o job (pronto/erro).
    Feito para rodar numa thread — abre a própria sessão do banco."""
    from app.services.jobs import atualizar

    try:
        from app.services.parser_renew import ler_renew
        from app.services.matcher import conciliar
        from app.services.persistencia import salvar_conciliacao
        from app.database import SessionLocal

        executor = runner or rodar_renew
        rel = executor(pasta, on_progress=lambda a, t: atualizar(
            job_id, fase="ocr", atual=a, total=t))
        atualizar(job_id, fase="conciliando")
        registros = ler_renew(rel)
        resultado = conciliar(autorizadas, canceladas, lancamentos, registros)
        info = dict(nomes or {})
        info["pasta_pdfs"] = str(pasta)
        db = SessionLocal()
        try:
            conc = salvar_conciliacao(db, cnpj, info, resultado)
            cid = conc.id
        finally:
            db.close()
        atualizar(job_id, fase="pronto", conciliacao_id=cid)
    except Exception as exc:
        atualizar(job_id, fase="erro", erro=str(exc))
