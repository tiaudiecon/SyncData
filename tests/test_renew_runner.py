import sys
import tempfile
from pathlib import Path
import pytest
from app.services import renew_runner
from app.services.jobs import criar_job, atualizar, estado


def _fake_script(ok, escreve_relatorio):
    linhas = [
        "import sys",
        "from pathlib import Path",
        "pasta = Path(sys.argv[1])",
        "(pasta / 'E_100.pdf').write_bytes(b'x')",   # 'renomeia' um PDF (progresso)
    ]
    if escreve_relatorio:
        linhas.append("(pasta / 'Relatório Renew.xlsx').write_bytes(b'x')")
    linhas.append("sys.exit(%d)" % (0 if ok else 2))
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8")
    f.write("\n".join(linhas)); f.close()
    return f.name


def test_jobs_ciclo():
    jid = criar_job(total=5)
    assert estado(jid)["fase"] == "ocr" and estado(jid)["total"] == 5
    atualizar(jid, fase="pronto", conciliacao_id=7)
    assert estado(jid)["fase"] == "pronto" and estado(jid)["conciliacao_id"] == 7
    assert estado("nao-existe") is None


def test_localizar_por_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNCDATA_RENEW_DIR", str(tmp_path))
    assert renew_runner.localizar_renew_dir() == tmp_path


def test_contar_pdfs_e_renomeados(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"x")
    (tmp_path / "b.PDF").write_bytes(b"x")
    (tmp_path / "E_a.pdf").write_bytes(b"x")
    (tmp_path / "nota.txt").write_bytes(b"x")
    assert renew_runner.contar_pdfs(tmp_path) == 3
    assert renew_runner.contar_renomeados(tmp_path) == 1


def test_rodar_renew_ok(tmp_path):
    prog = []
    rel = renew_runner.rodar_renew(
        str(tmp_path), comando=[sys.executable, _fake_script(True, True)],
        on_progress=lambda a, t: prog.append((a, t)), intervalo=0.02)
    assert rel.name == "Relatório Renew.xlsx" and rel.is_file()
    assert prog and prog[-1] == (renew_runner.contar_pdfs(tmp_path),
                                 renew_runner.contar_pdfs(tmp_path))


def test_rodar_renew_falha(tmp_path):
    with pytest.raises(RuntimeError):
        renew_runner.rodar_renew(
            str(tmp_path), comando=[sys.executable, _fake_script(False, False)],
            intervalo=0.02)


def test_rodar_renew_sem_relatorio_levanta(tmp_path):
    with pytest.raises(RuntimeError):
        renew_runner.rodar_renew(
            str(tmp_path), comando=[sys.executable, _fake_script(True, False)],
            intervalo=0.02)
