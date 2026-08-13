import io
import tempfile
from pathlib import Path
from datetime import datetime
import openpyxl
from app.services.jobs import criar_job, estado
from app.services.renew_runner import processar_pasta
from app.services.parser_spdata import ler_spdata
from app.services.parser_sieg import ler_sieg

_RENEW_COLS = ["Status", "Tipo de Nota", "Nome Original", "Novo Nome",
               "Fornecedor Emitente", "CNPJ do Emissor", "Nº NF / Série",
               "Data de Emissão", "Valor da NF"]


def escrever_relatorio_renew(pasta, linhas=None):
    if linhas is None:
        linhas = [["OK", "SERVICO", "orig.pdf", "E_100.pdf", "FORNEC A",
                   "11.111.111/0001-11", "100", datetime(2026, 7, 3), 150]]
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(_RENEW_COLS)
    for ln in linhas:
        ws.append(ln)
    caminho = Path(pasta) / "Relatório Renew.xlsx"
    wb.save(str(caminho))
    return caminho


def fake_runner(pasta, on_progress=None):
    """Substitui o Renew real: escreve o relatório e sinaliza progresso."""
    caminho = escrever_relatorio_renew(pasta)
    if on_progress:
        on_progress(1, 1)
    return caminho


def pasta_com_pdf():
    pasta = tempfile.mkdtemp(prefix="syncdata_pdfs_")
    (Path(pasta) / "nota.pdf").write_bytes(b"%PDF-1.4 x")
    return pasta


def montar_conciliacao(cnpj, spdata_bytes, sieg_bytes, pasta=None):
    """Cria uma Conciliação pelo caminho novo (sem web), com um Renew falso.
    Devolve o estado do job (contém 'conciliacao_id')."""
    pasta = pasta or tempfile.mkdtemp(prefix="syncdata_pdfs_")
    lancamentos = ler_spdata(spdata_bytes)
    autorizadas, canceladas = ler_sieg(io.BytesIO(sieg_bytes), cnpj)
    jid = criar_job()
    processar_pasta(jid, pasta, autorizadas, canceladas, lancamentos, cnpj,
                    nomes={"spdata": "SpData.txt", "sieg": "sieg.xlsx"},
                    runner=fake_runner)
    return estado(jid)
