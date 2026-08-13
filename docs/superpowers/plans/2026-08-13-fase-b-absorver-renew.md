# Fase B — SyncData absorve o Renew + Preview de PDF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fazer o SyncData rodar o Renew por baixo (um único executável): apontar a pasta de PDFs → o SyncData roda o Renew nela com barra de progresso ao vivo → lê a saída → concilia → mostra o caminho do PDF de cada nota arquivada com preview embutido e abrir em segunda tela.

**Architecture:** A frente de "arquivo" continua vindo do `Relatório Renew.xlsx` (parser atual), mas a planilha agora nasce automática na pasta em vez de ser enviada. O upload do Renew `.xlsx` some; entra um seletor de pasta nativo. Um serviço novo (`renew_runner`) roda o Renew como subprocess e acompanha o progresso; um registro de jobs em memória guarda o estado; a tela de "Processando" faz polling. O `RegistroRenew` passa a capturar o nome do PDF ("Novo Nome"), o matcher leva o candidato do Renew casado até o item, e o item guarda `arquivo_pdf`; a `Conciliacao` guarda `pasta_pdfs`. Uma rota `/pdf/{item}` serve o arquivo (com trava de caminho) para o preview.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy/SQLite, openpyxl, PyInstaller, pytest (tudo já no `venv`). Windows-only (seletor de pasta via PowerShell).

## Global Constraints

- **Ambiente:** repo em `D:\William Lopes - Docs\Documentos\Audiecon\Automocoes\SyncData`. O shell **reseta o cwd** — todo comando Bash começa com `cd "D:/William Lopes - Docs/Documentos/Audiecon/Automocoes/SyncData" && ...`. Trabalhar numa **branch** (não `main`). Testes: `venv/Scripts/python.exe -m pytest -q -W error::DeprecationWarning`.
- **Contrato do Renew (CLI):** `Renew_10.4.exe "C:\pasta"`. Ele gera na pasta o arquivo de nome fixo **`Relatório Renew.xlsx`** e renomeia os PDFs processados para o padrão **`E_*.pdf`** (E = entrada). Sem argumento ele abriria a GUI — por isso sempre passamos a pasta.
- **Localização do Renew (embutido):** `renew_runner.localizar_renew_dir()` usa o env `SYNCDATA_RENEW_DIR`; quando congelado (`sys.frozen`), usa `<sys._MEIPASS>/renew`. Nome do exe: env `SYNCDATA_RENEW_EXE` (default `Renew_10.4.exe`).
- **Sinal de progresso:** primário/concreto = contar os PDFs já renomeados (`E_*.pdf`) vs. o total de PDFs. (Refinar com o parse do stdout do Renew é ponto de calibração posterior, fora deste plano.)
- **Valor do Renew = BRUTO:** a base de comparação da frente de arquivo (`_cmp_renew`) **não muda** — continua `nota.valor_servico` (calibração da Fase A). Este plano só adiciona o `arquivo_pdf`.
- **Banco:** recriado (colunas novas são **nullable**) — pré-produção. Nos testes o `conftest.py` já cria um SQLite temporário novo por processo, então o schema nasce com as colunas novas.
- **Preview:** painel lateral com `<iframe src="/pdf/{item}">` + botão **"Abrir"** (`target="_blank"`, segunda tela). A rota `/pdf/{item}` só serve arquivos **dentro** de `Conciliacao.pasta_pdfs` (trava contra path traversal); arquivo ausente/pasta movida → 404.
- **Campos novos (schema fixo em todo o plano):**
  - `RegistroRenew.arquivo_pdf: str = ""` (coluna "Novo Nome").
  - `matcher.ItemConciliacao.arquivo_row: object = None` (o `RegistroRenew` casado, ou None).
  - `Conciliacao.pasta_pdfs` (String, nullable); `ConciliacaoItem.arquivo_pdf` (String, nullable).
- **Estado do job (dict):** `{"fase": "ocr"|"conciliando"|"pronto"|"erro", "atual": int, "total": int, "conciliacao_id": int|None, "erro": str|None}`.

---

### Task 1: Parser Renew — capturar "Novo Nome" (arquivo_pdf)

**Files:**
- Modify: `app/services/parser_renew.py`
- Test: `tests/test_parser_renew.py`

**Interfaces:**
- Produces: `RegistroRenew` ganha o campo `arquivo_pdf: str = ""`, preenchido a partir da coluna **"Novo Nome"** (opcional — ausente vira `""`).

- [ ] **Step 1: Escrever o teste** — adicionar em `tests/test_parser_renew.py` (o `HEADERS` do arquivo já inclui `"Novo Nome"` na posição 3 e o `_xlsx` já existe):

```python
def test_captura_novo_nome_como_arquivo_pdf():
    arq = _xlsx(
        ["OK", "PRODUTO", "x.pdf", "E_2026-05-11_NF202069.pdf", "VITORIA HOSPITALAR LTDA",
         "39.362.611/0001-15", "202069 / 7", datetime(2026, 5, 11), 1800],
    )
    it = ler_renew(arq)[0]
    assert it.arquivo_pdf == "E_2026-05-11_NF202069.pdf"


def test_sem_coluna_novo_nome_fica_vazio():
    headers = [h for h in HEADERS if h != "Novo Nome"]
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(headers)
    ws.append(["OK", "PRODUTO", "x.pdf", "VITORIA HOSPITALAR LTDA",
               "39.362.611/0001-15", "202069 / 7", datetime(2026, 5, 11), 1800])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    it = ler_renew(buf)[0]
    assert it.arquivo_pdf == ""
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_parser_renew.py::test_captura_novo_nome_como_arquivo_pdf -v` → FAIL (`arquivo_pdf` inexistente).

- [ ] **Step 3: Implementar** — em `app/services/parser_renew.py`:

(a) adicionar o campo no dataclass (depois de `valor`):
```python
@dataclass
class RegistroRenew:
    numero: str
    numero_norm: str
    cnpj_emissor: str
    fornecedor: str
    emissao: "date | None"
    valor: float          # `Valor da NF` = valor de FACE/BRUTO da nota
    arquivo_pdf: str = ""  # `Novo Nome` = nome do PDF renomeado pelo Renew
```

(b) em `ler_renew`, após `i_val = indice(mapa, "Valor da NF")`:
```python
    i_pdf = indice(mapa, "Novo Nome")
```

(c) no append de `RegistroRenew`, acrescentar o argumento:
```python
        itens.append(RegistroRenew(
            numero=numero,
            numero_norm=normalizar_numero_nf(numero),
            cnpj_emissor=so_digitos(val(row, i_cnpj)),
            fornecedor=str(val(row, i_forn) or "").strip(),
            emissao=para_data(val(row, i_emi)),
            valor=limpar_moeda(val(row, i_val)),
            arquivo_pdf=str(val(row, i_pdf) or "").strip(),
        ))
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_parser_renew.py -v` → PASS (todos, incl. os antigos).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: parser Renew captura o nome do PDF (Novo Nome -> arquivo_pdf)"`

---

### Task 2: Matcher — carregar o candidato do Renew casado (arquivo_row)

**Files:**
- Modify: `app/services/matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `RegistroRenew` (Task 1).
- Produces: `ItemConciliacao` ganha `arquivo_row: object = None` (o `RegistroRenew` casado na frente de arquivo, ou None). `conciliar` passa a capturar o candidato do Renew.

- [ ] **Step 1: Escrever os testes** — adicionar em `tests/test_matcher.py` (o `reg()` já existe e cria um `RegistroRenew`; aceita `arquivo_pdf`? Ainda não — usar o default e checar por identidade do objeto):

```python
def test_item_carrega_registro_renew_casado():
    r = conciliar([nota()], [], [lanc()], [reg()])
    assert r.itens[0].arquivo_row is not None
    assert r.itens[0].arquivo_row.cnpj_emissor == "11111111000111"


def test_faltou_arquivar_sem_registro_renew():
    r = conciliar([nota()], [], [lanc()], [])   # nada no Renew
    assert r.itens[0].arquivo.status == STATUS_FALTA
    assert r.itens[0].arquivo_row is None
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_matcher.py -k "registro_renew or sem_registro" -v` → FAIL (`arquivo_row` inexistente).

- [ ] **Step 3: Implementar** — em `app/services/matcher.py`:

(a) `ItemConciliacao` ganha o campo (depois de `lancamento_row`):
```python
@dataclass
class ItemConciliacao:
    nota: object
    lancamento: Frente
    arquivo: Frente
    veredito: str = "pendente"
    lancamento_row: object = None
    arquivo_row: object = None
```

(b) em `conciliar`, capturar o candidato do Renew e passá-lo ao item (substituir o corpo do laço `for nota in autorizadas`):
```python
    for nota in autorizadas:
        lanc, lanc_row = _avaliar(nota, idx_sp.get(nota.cnpj_prestador, []), _cmp_spdata)
        arq, arq_row = _avaliar(nota, idx_rn.get(nota.cnpj_prestador, []), _cmp_renew)
        veredito = _veredito(lanc, arq)
        res.itens.append(ItemConciliacao(nota, lanc, arq, veredito, lanc_row, arq_row))

        if lanc.status == STATUS_FALTA:
            res.qt_falta_lancar += 1
        if arq.status == STATUS_FALTA:
            res.qt_falta_arquivar += 1
        if veredito == "gerenciada":
            res.qt_gerenciadas += 1
        elif veredito == "ressalva":
            res.qt_ressalva += 1
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_matcher.py -v` → PASS (todos, incl. os antigos).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: matcher leva o registro do Renew casado ao item (arquivo_row)"`

---

### Task 3: Modelo + persistência — pasta_pdfs e arquivo_pdf

**Files:**
- Modify: `app/models.py`
- Modify: `app/services/persistencia.py`
- Test: `tests/test_persistencia.py`

**Interfaces:**
- Consumes: `ItemConciliacao.arquivo_row` (Task 2), `RegistroRenew.arquivo_pdf` (Task 1).
- Produces: `Conciliacao.pasta_pdfs` (String, nullable); `ConciliacaoItem.arquivo_pdf` (String, nullable). `salvar_conciliacao(db, cnpj, nomes, resultado)` lê `nomes.get("pasta_pdfs")` e grava `arquivo_pdf` do `arquivo_row`.

- [ ] **Step 1: Escrever o teste** — adicionar em `tests/test_persistencia.py`:

```python
def test_persiste_pasta_e_arquivo_pdf(client):
    from app.services.parser_renew import RegistroRenew
    from app.database import SessionLocal
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3), 150.0, 150.0, False)
    l = LancamentoSpData("100", "100", "11111111000111", "F", date(2026, 7, 3), 150.0, 150.0)
    reg = RegistroRenew("100", "100", "11111111000111", "F", date(2026, 7, 3), 150.0,
                        arquivo_pdf="E_100.pdf")
    res = conciliar([n], [], [l], [reg])
    db = SessionLocal()
    conc = salvar_conciliacao(db, "04541288000162",
                              {"spdata": "a", "sieg": "b", "pasta_pdfs": r"C:\pdfs"}, res)
    it = db.query(ConciliacaoItem).filter_by(conciliacao_id=conc.id).first()
    assert conc.pasta_pdfs == r"C:\pdfs"
    assert it.arquivo_pdf == "E_100.pdf"
    db.close()
```

(O `test_persistencia.py` já importa `NotaSieg`, `LancamentoSpData`, `conciliar`, `salvar_conciliacao`, `ConciliacaoItem`, `date` no topo — confira e reaproveite; o parâmetro `client` garante `create_all` + limpeza das tabelas.)

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_persistencia.py::test_persiste_pasta_e_arquivo_pdf -v` → FAIL (colunas inexistentes).

- [ ] **Step 3a: Implementar — `app/models.py`**:

Em `Conciliacao`, após `qt_canceladas = Column(...)` (antes de `itens = relationship(...)`):
```python
    pasta_pdfs = Column(String, nullable=True)
```

Em `ConciliacaoItem`, após `impostos_json = Column(String, default="")` (antes de `conciliacao = relationship(...)`):
```python
    arquivo_pdf = Column(String, nullable=True)
```

- [ ] **Step 3b: Implementar — `app/services/persistencia.py`**:

(a) na criação de `Conciliacao(...)`, acrescentar o argumento (o `arquivo_renew_nome` continua, agora recebe `None` no fluxo novo):
```python
        qt_canceladas=resultado.qt_canceladas,
        pasta_pdfs=nomes.get("pasta_pdfs"),
    )
```

(b) no `ConciliacaoItem(...)` dentro do laço, acrescentar (depois de `impostos_json=...`):
```python
            impostos_json=_impostos_json(n, sp),
            arquivo_pdf=(item.arquivo_row.arquivo_pdf if item.arquivo_row else None),
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_persistencia.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: Conciliacao guarda pasta_pdfs e o item guarda arquivo_pdf"`

---

### Task 4: Seletor de pasta nativo (PowerShell)

**Files:**
- Create: `app/services/seletor_pasta.py`
- Test: `tests/test_seletor_pasta.py` (novo)

**Interfaces:**
- Produces: `escolher_pasta() -> str | None` (abre a janela nativa do Windows; None se cancelado); `_parse_saida(stdout) -> str | None` (isola o parse, testável).

- [ ] **Step 1: Escrever o teste `tests/test_seletor_pasta.py`**

```python
from app.services.seletor_pasta import _parse_saida


def test_parse_pega_o_caminho():
    assert _parse_saida("C:\\Users\\W\\PDFs\n") == r"C:\Users\W\PDFs"


def test_parse_vazio_vira_none():
    assert _parse_saida("") is None
    assert _parse_saida("\n  \n") is None


def test_parse_usa_a_ultima_linha():
    # PowerShell pode imprimir ruído antes; o caminho é a última linha não-vazia.
    assert _parse_saida("aviso\nC:\\PDFs\n") == r"C:\PDFs"
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_seletor_pasta.py -v` → FAIL (módulo inexistente).

- [ ] **Step 3: Implementar `app/services/seletor_pasta.py`**

```python
import subprocess

_PS = r'''
Add-Type -AssemblyName System.Windows.Forms
$dlg = New-Object System.Windows.Forms.FolderBrowserDialog
$dlg.Description = "Selecione a pasta com os PDFs das notas"
$dono = New-Object System.Windows.Forms.Form
$dono.TopMost = $true
if ($dlg.ShowDialog($dono) -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dlg.SelectedPath
}
'''


def _parse_saida(stdout) -> "str | None":
    """Última linha não-vazia do stdout = o caminho escolhido."""
    linhas = [l.strip() for l in (stdout or "").splitlines() if l.strip()]
    return linhas[-1] if linhas else None


def escolher_pasta() -> "str | None":
    """Abre o seletor de pasta nativo do Windows (o servidor roda na máquina do
    usuário). Devolve o caminho escolhido, ou None se cancelado/erro."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", _PS],
            capture_output=True, text=True, timeout=300,
        )
    except Exception:
        return None
    return _parse_saida(r.stdout)
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_seletor_pasta.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: seletor de pasta nativo do Windows (FolderBrowserDialog via PowerShell)"`

---

### Task 5: Registro de jobs + runner do Renew (subprocess + progresso)

**Files:**
- Create: `app/services/jobs.py`, `app/services/renew_runner.py`
- Test: `tests/test_renew_runner.py` (novo)

**Interfaces:**
- Produces:
  - `jobs.criar_job(total=0) -> str`; `jobs.atualizar(job_id, **kw)`; `jobs.estado(job_id) -> dict | None`.
  - `renew_runner.localizar_renew_dir() -> Path`; `localizar_renew_exe() -> Path`; `contar_pdfs(pasta) -> int`; `contar_renomeados(pasta) -> int`.
  - `renew_runner.rodar_renew(pasta, comando=None, cwd=None, on_progress=None, intervalo=1.0) -> Path` — roda o Renew, chama `on_progress(atual, total)` durante a execução e devolve o caminho do `Relatório Renew.xlsx`; levanta `RuntimeError` se o código de saída for != 0 ou faltar o relatório.

- [ ] **Step 1: Escrever o teste `tests/test_renew_runner.py`**

```python
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
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_renew_runner.py -v` → FAIL (módulos inexistentes).

- [ ] **Step 3a: Implementar `app/services/jobs.py`**

```python
import uuid

_JOBS: "dict[str, dict]" = {}


def criar_job(total: int = 0) -> str:
    jid = uuid.uuid4().hex
    _JOBS[jid] = {"fase": "ocr", "atual": 0, "total": total,
                  "conciliacao_id": None, "erro": None}
    return jid


def atualizar(job_id: str, **kw) -> None:
    job = _JOBS.get(job_id)
    if job is not None:
        job.update(kw)


def estado(job_id: str) -> "dict | None":
    return _JOBS.get(job_id)
```

- [ ] **Step 3b: Implementar `app/services/renew_runner.py`**

```python
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
    total = contar_pdfs(pasta)
    proc = subprocess.Popen([*comando, str(pasta)], cwd=cwd,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    while proc.poll() is None:
        if on_progress:
            on_progress(contar_renomeados(pasta), total)
        time.sleep(intervalo)
    saida = proc.stdout.read() if proc.stdout else ""
    if proc.returncode != 0:
        cauda = "\n".join(saida.splitlines()[-8:])
        raise RuntimeError(f"O Renew falhou (código {proc.returncode}).\n{cauda}")
    if on_progress:
        on_progress(total, total)
    rel = pasta / RELATORIO_NOME
    if not rel.is_file():
        raise RuntimeError("O Renew rodou mas não gerou o 'Relatório Renew.xlsx'.")
    return rel
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_renew_runner.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: jobs em memoria + renew_runner (roda o Renew via subprocess com progresso)"`

---

### Task 6: Orquestração — processar_pasta + helpers de teste

**Files:**
- Modify: `app/services/renew_runner.py` (acrescenta `processar_pasta`)
- Create: `tests/_fakes.py` (helpers compartilhados; **não** é arquivo de teste coletável)
- Test: `tests/test_processar_pasta.py` (novo)

**Interfaces:**
- Consumes: `rodar_renew` (Task 5), `jobs.atualizar`, `parser_renew.ler_renew`, `matcher.conciliar`, `persistencia.salvar_conciliacao`, `database.SessionLocal`.
- Produces: `renew_runner.processar_pasta(job_id, pasta, autorizadas, canceladas, lancamentos, cnpj, nomes=None, runner=None)` — roda o runner, lê o `Relatório Renew.xlsx`, concilia, salva (com `pasta_pdfs`) e atualiza o job para `pronto`/`erro`. Quando `runner=None`, usa `rodar_renew` (resolvido por nome no módulo, para permitir monkeypatch nos testes).
- Produces (test helpers): `tests/_fakes.escrever_relatorio_renew(pasta, linhas=None)`, `fake_runner(pasta, on_progress=None)`, `pasta_com_pdf()`, `montar_conciliacao(cnpj, spdata_bytes, sieg_bytes, pasta=None) -> dict`.

- [ ] **Step 1: Escrever os helpers `tests/_fakes.py`**

```python
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
```

- [ ] **Step 2: Escrever o teste `tests/test_processar_pasta.py`**

```python
from tests.test_conciliar import _sieg_xlsx, _spdata_txt
from tests._fakes import montar_conciliacao
from app.database import SessionLocal
from app.models import Conciliacao, ConciliacaoItem


def test_processar_pasta_salva_conciliacao(client):
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    assert st["fase"] == "pronto"
    assert st["conciliacao_id"]
    db = SessionLocal()
    conc = db.query(Conciliacao).get(st["conciliacao_id"])
    it = db.query(ConciliacaoItem).filter_by(conciliacao_id=conc.id).first()
    db.close()
    assert conc.pasta_pdfs
    assert it.arquivo_pdf == "E_100.pdf"
    assert it.veredito == "gerenciada"


def test_processar_pasta_marca_erro_quando_runner_falha(client):
    from app.services.jobs import criar_job, estado
    from app.services.renew_runner import processar_pasta

    def runner_ruim(pasta, on_progress=None):
        raise RuntimeError("boom")

    jid = criar_job()
    processar_pasta(jid, "qualquer", [], [], [], "04541288000162", runner=runner_ruim)
    assert estado(jid)["fase"] == "erro"
    assert "boom" in estado(jid)["erro"]
```

- [ ] **Step 3: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_processar_pasta.py -v` → FAIL (`processar_pasta` inexistente).

- [ ] **Step 4: Implementar** — acrescentar ao fim de `app/services/renew_runner.py`:

```python
def processar_pasta(job_id, pasta, autorizadas, canceladas, lancamentos, cnpj,
                    nomes=None, runner=None):
    """Roda o Renew na pasta, concilia e salva. Atualiza o job (pronto/erro).
    Feito para rodar numa thread — abre a própria sessão do banco."""
    from app.services.jobs import atualizar
    from app.services.parser_renew import ler_renew
    from app.services.matcher import conciliar
    from app.services.persistencia import salvar_conciliacao
    from app.database import SessionLocal

    executor = runner or rodar_renew
    try:
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
```

- [ ] **Step 5: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_processar_pasta.py -v` → PASS.

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: processar_pasta orquestra Renew->conciliacao->banco (com helpers de teste)"`

---

### Task 7: Fluxo web — POST /conciliar (job) + rotas de progresso + telas

**Files:**
- Modify: `app/routers/conciliar.py`
- Create: `app/routers/processar.py`
- Modify: `app/main.py`
- Modify: `templates/conciliar.html`
- Create: `templates/processando.html`
- Modify: `static/css/syncdata.css`
- Test: `tests/test_conciliar.py` (reescreve), `tests/test_resultado.py` (adapta), `tests/test_impostos.py` (adapta)

**Interfaces:**
- Consumes: `renew_runner.contar_pdfs/processar_pasta`, `jobs.criar_job/estado`, `seletor_pasta.escolher_pasta`.
- Produces: `POST /conciliar` (valida pasta + lê spdata/sieg, dispara o job, devolve `processando.html` com `job_id`); `GET /processar/{job_id}` (JSON do estado, 404 se desconhecido); `GET /procurar-pasta` (JSON `{"pasta": ...}`).

- [ ] **Step 1: Escrever/reescrever os testes**

(a) **Substituir** `tests/test_conciliar.py` (manter os helpers `_sieg_xlsx`, `_renew_xlsx`, `_spdata_txt` como estão; trocar os dois testes de fluxo):
```python
# ... manter os helpers _sieg_xlsx / _renew_xlsx / _spdata_txt existentes ...

import re
import time
from tests._fakes import pasta_com_pdf, fake_runner
from app.services import renew_runner


def _poll(client, jid, timeout=5.0):
    fim = time.time() + timeout
    ultimo = None
    while time.time() < fim:
        ultimo = client.get(f"/processar/{jid}").json()
        if ultimo.get("fase") in ("pronto", "erro"):
            return ultimo
        time.sleep(0.05)
    return ultimo


def test_fluxo_conciliar_gerenciada(client, monkeypatch):
    monkeypatch.setattr(renew_runner, "rodar_renew", fake_runner)
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar",
                       data={"pasta": pasta_com_pdf()},
                       files={"spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
                              "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"),
                                       "application/octet-stream")})
    assert resp.status_code == 200
    m = re.search(r'data-job="([0-9a-f]+)"', resp.text)
    assert m
    s = _poll(client, m.group(1))
    assert s["fase"] == "pronto"
    assert client.get(f"/resultado/{s['conciliacao_id']}").status_code == 200


def test_arquivo_trocado_no_campo_sieg_mostra_erro_claro(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar",
                       data={"pasta": pasta_com_pdf()},
                       files={"spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
                              "sieg": ("renew.xlsx", _renew_xlsx(),  # arquivo errado
                                       "application/octet-stream")})
    assert resp.status_code == 200
    assert "Não consegui ler" in resp.text


def test_pasta_inexistente_avisa(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar",
                       data={"pasta": r"C:\pasta\que\nao\existe"},
                       files={"spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
                              "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"),
                                       "application/octet-stream")})
    assert resp.status_code == 200
    assert "não existe" in resp.text.lower()
```

(b) **Adaptar** `tests/test_resultado.py` — trocar as 3 chamadas `client.post("/conciliar", files=...)` por `montar_conciliacao(...)`:
```python
import io
import openpyxl
from tests.test_conciliar import _sieg_xlsx, _spdata_txt
from tests._fakes import montar_conciliacao


def test_montar_itens_enriquecido(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    from app.database import SessionLocal
    from app.models import Conciliacao
    from app.routers.resultado import montar_resumo_e_itens
    db = SessionLocal()
    conc = db.query(Conciliacao).order_by(Conciliacao.id.desc()).first()
    resumo, itens = montar_resumo_e_itens(conc)
    db.close()
    assert itens
    it = itens[0]
    for chave in ("sieg_bruto", "sieg_liquido", "sieg_imp", "sp_bruto", "impostos", "tem_desconto"):
        assert chave in it
    assert it["numero"].isdigit()


def test_resultado_tem_busca_e_grupos(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    html = client.get(f"/resultado/{st['conciliacao_id']}").text
    assert 'id="busca"' in html
    assert "Ver impostos" in html


def test_resultado_e_export(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    destino = f"/resultado/{st['conciliacao_id']}"
    assert client.get(destino).status_code == 200
    planilha = client.get(destino + "/planilha.xlsx")
    assert planilha.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(planilha.content))
    assert wb.sheetnames == ["Conciliação", "Faltou Lançar", "Faltou Arquivar", "Impostos"]
```

(c) **Adaptar** `tests/test_impostos.py`:
```python
from tests.test_conciliar import _sieg_xlsx, _spdata_txt
from tests._fakes import montar_conciliacao


def test_impostos_renderiza(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Detalhamento de Impostos" in r.text
    assert "CSRF" in r.text


def test_impostos_vazio_sem_conciliacao(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Nenhuma conciliação" in r.text
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_conciliar.py -v` → FAIL (`/conciliar` ainda espera `renew`; `/processar` inexistente).

- [ ] **Step 3a: Implementar — `app/routers/conciliar.py`** (substituir o arquivo):

```python
import io
import os
import threading
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.configuracao import esta_configurado, obter_config, contexto_cliente
from app.services.parser_spdata import ler_spdata
from app.services.parser_sieg import ler_sieg
from app.services.renew_runner import contar_pdfs, processar_pasta
from app.services.jobs import criar_job

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    if not esta_configurado(db):
        return RedirectResponse(url="/setup", status_code=303)
    return templates.TemplateResponse(request, "conciliar.html", {
        "ativo": "conciliar", "erro": None, **contexto_cliente(db),
    })


def _erro(request, db, msg):
    return templates.TemplateResponse(request, "conciliar.html", {
        "ativo": "conciliar", "erro": msg, **contexto_cliente(db),
    })


@router.post("/conciliar")
async def executar(request: Request, db: Session = Depends(get_db),
                   spdata: UploadFile = File(...), sieg: UploadFile = File(...),
                   pasta: str = Form(...)):
    cfg = obter_config(db)
    pasta_lim = (pasta or "").strip()
    if not pasta_lim or not os.path.isdir(pasta_lim):
        return _erro(request, db, "Selecione a pasta dos PDFs — o caminho informado não existe.")
    if contar_pdfs(pasta_lim) == 0:
        return _erro(request, db, "A pasta selecionada não tem nenhum PDF.")
    try:
        lancamentos = ler_spdata(await spdata.read())
        autorizadas, canceladas = ler_sieg(io.BytesIO(await sieg.read()), cfg.cnpj_cliente)
    except Exception as exc:   # arquivo trocado/ilegível: avisa na própria tela
        return _erro(request, db, f"Não consegui ler um dos arquivos: {exc}")

    jid = criar_job(total=contar_pdfs(pasta_lim))
    nomes = {"spdata": spdata.filename, "sieg": sieg.filename}
    threading.Thread(
        target=processar_pasta,
        args=(jid, pasta_lim, autorizadas, canceladas, lancamentos, cfg.cnpj_cliente, nomes),
        daemon=True,
    ).start()
    return templates.TemplateResponse(request, "processando.html", {
        "ativo": "conciliar", "job_id": jid, **contexto_cliente(db),
    })
```

- [ ] **Step 3b: Implementar — `app/routers/processar.py`**

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.services.jobs import estado
from app.services.seletor_pasta import escolher_pasta

router = APIRouter()


@router.get("/procurar-pasta")
def procurar_pasta():
    return JSONResponse({"pasta": escolher_pasta()})


@router.get("/processar/{job_id}")
def status_job(job_id: str):
    s = estado(job_id)
    if s is None:
        return JSONResponse({"erro": "job desconhecido"}, status_code=404)
    return JSONResponse(s)
```

- [ ] **Step 3c: Implementar — `app/main.py`** (registrar o router; adicionar às importações e ao `include_router`):
```python
from app.routers import impostos
from app.routers import processar
```
```python
app.include_router(impostos.router)
app.include_router(processar.router)
```

- [ ] **Step 3d: Implementar — `templates/conciliar.html`** (substituir o arquivo):
```html
{% extends "base.html" %}
{% block titulo %}Conciliar · SyncData{% endblock %}
{% block content %}
<div class="page-head">
  <div><div class="crumb">Nova conciliação</div><h1>Conciliar <em>notas</em></h1></div>
</div>

{% if erro %}<div class="erro-box">{{ erro }}</div>{% endif %}

<form method="post" action="/conciliar" enctype="multipart/form-data">
  <div class="panel">
    <div class="panel-head"><h3>Envie os arquivos do período</h3></div>
    <div class="panel-body">
      <div class="upload">
        <div class="num">1</div>
        <div class="meta"><div class="t">SpData</div><div class="h">Lançamentos do cliente · arquivo .txt</div></div>
        <input type="file" name="spdata" accept=".txt" required>
      </div>
      <div class="upload">
        <div class="num">2</div>
        <div class="meta"><div class="t">Sieg — Serviço</div><div class="h">NFS-e, a lista-mestra · arquivo .xlsx</div></div>
        <input type="file" name="sieg" accept=".xlsx" required>
      </div>
      <div class="upload">
        <div class="num">3</div>
        <div class="meta"><div class="t">Pasta dos PDFs</div><div class="h">Notas arquivadas · o SyncData processa com o Renew</div></div>
        <div style="display:flex; gap:8px; flex:1; min-width:0">
          <input type="text" id="pasta" name="pasta" class="input" style="flex:1"
                 placeholder="Escolha a pasta com os PDFs…" required readonly>
          <button type="button" class="btn btn-ghost" onclick="procurarPasta()">Procurar…</button>
        </div>
      </div>

      <div class="note-box">O SyncData roda o <strong>Renew</strong> nessa pasta (renomeia e
        extrai as notas) e concilia. A primeira leitura de PDFs escaneados pode levar alguns minutos.</div>

      <div style="margin-top:20px">
        <button class="btn btn-accent btn-lg" type="submit">
          <svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
          Conciliar
        </button>
      </div>
    </div>
  </div>
</form>

<script>
  const campoPasta = document.getElementById('pasta');
  const ultimo = localStorage.getItem('syncdata_pasta');
  if (ultimo) { campoPasta.value = ultimo; }
  async function procurarPasta(){
    try{
      const r = await fetch('/procurar-pasta');
      const d = await r.json();
      if (d.pasta){ campoPasta.value = d.pasta; localStorage.setItem('syncdata_pasta', d.pasta); }
    }catch(e){}
  }
</script>
{% endblock %}
```

- [ ] **Step 3e: Implementar — `templates/processando.html`** (criar):
```html
{% extends "base.html" %}
{% block titulo %}Processando · SyncData{% endblock %}
{% block content %}
<div class="page-head">
  <div><div class="crumb">Nova conciliação</div><h1>Processando notas</h1></div>
</div>
<div class="panel"><div class="panel-body">
  <div id="proc" data-job="{{ job_id }}">
    <div id="fase" class="sub">Lendo os PDFs e extraindo as notas…</div>
    <div class="prog"><div id="barra" class="prog-fill" style="width:5%"></div></div>
    <div id="cont" class="mono" style="margin-top:8px">0 / 0</div>
    <div id="erro" class="erro-box" style="display:none; margin-top:16px"></div>
  </div>
</div></div>
<script>
  const jid = document.getElementById('proc').dataset.job;
  async function poll(){
    try{
      const r = await fetch('/processar/' + jid);
      if (r.status !== 404){
        const s = await r.json();
        if (s.fase === 'conciliando'){
          document.getElementById('fase').textContent = 'Conferindo lançamentos e arquivamento…';
        }
        const total = s.total || 0, atual = s.atual || 0;
        const pct = total ? Math.round(atual * 100 / total) : (s.fase === 'conciliando' ? 95 : 5);
        document.getElementById('barra').style.width = pct + '%';
        document.getElementById('cont').textContent = atual + ' / ' + total;
        if (s.fase === 'pronto' && s.conciliacao_id){
          window.location = '/resultado/' + s.conciliacao_id; return;
        }
        if (s.fase === 'erro'){
          const e = document.getElementById('erro');
          e.style.display = 'block'; e.textContent = s.erro || 'Falha ao processar.';
          document.getElementById('fase').textContent = 'Não foi possível concluir.';
          return;
        }
      }
    }catch(e){}
    setTimeout(poll, 1000);
  }
  poll();
</script>
{% endblock %}
```

- [ ] **Step 3f: Implementar — CSS** (adicionar ao fim de `static/css/syncdata.css`):
```css
.prog{height:12px; background:var(--surface-2); border:1px solid var(--line-2);
  border-radius:999px; overflow:hidden; margin-top:14px}
.prog-fill{height:100%; background:var(--navy); border-radius:999px; transition:width .4s ease}
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_conciliar.py tests/test_resultado.py tests/test_impostos.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: /conciliar aponta pasta e roda o Renew em job com tela de progresso"`

---

### Task 8: Rota /pdf + coluna PDF na tela de Resultado (preview + abrir)

**Files:**
- Create: `app/routers/pdf.py`
- Modify: `app/main.py`
- Modify: `app/routers/resultado.py` (expor `id` e `arquivo_pdf` no item)
- Modify: `templates/resultado.html`
- Modify: `static/css/syncdata.css`
- Test: `tests/test_pdf.py` (novo), `tests/test_resultado.py` (uma asserção nova)

**Interfaces:**
- Consumes: `ConciliacaoItem.arquivo_pdf`, `Conciliacao.pasta_pdfs`.
- Produces: `GET /pdf/{item_id}` (serve o PDF inline com trava de caminho; 404 se ausente). `montar_resumo_e_itens` passa a incluir `"id"` e `"arquivo_pdf"` em cada item.

- [ ] **Step 1: Escrever os testes**

(a) `tests/test_pdf.py` (novo):
```python
import os
import tempfile
from app.database import SessionLocal
from app.models import Conciliacao, ConciliacaoItem


def _conc_com_pdf(pasta, arquivo_pdf):
    db = SessionLocal()
    c = Conciliacao(cnpj="04541288000162", pasta_pdfs=pasta)
    db.add(c); db.flush()
    it = ConciliacaoItem(conciliacao_id=c.id, numero="100",
                         arquivo_pdf=arquivo_pdf, status_arquivo="ok")
    db.add(it); db.commit()
    iid = it.id
    db.close()
    return iid


def test_serve_pdf_inline(client):
    pasta = tempfile.mkdtemp(prefix="pdf_")
    with open(os.path.join(pasta, "E_100.pdf"), "wb") as f:
        f.write(b"%PDF-1.4 fake")
    iid = _conc_com_pdf(pasta, "E_100.pdf")
    r = client.get(f"/pdf/{iid}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"


def test_bloqueia_path_traversal(client):
    pasta = tempfile.mkdtemp(prefix="pdf_")
    iid = _conc_com_pdf(pasta, "..\\..\\segredo.pdf")
    assert client.get(f"/pdf/{iid}").status_code == 404


def test_pdf_ausente_404(client):
    pasta = tempfile.mkdtemp(prefix="pdf_")
    iid = _conc_com_pdf(pasta, "nao_existe.pdf")
    assert client.get(f"/pdf/{iid}").status_code == 404
```

(b) `tests/test_resultado.py` — acrescentar:
```python
def test_resultado_mostra_botao_pdf(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    st = montar_conciliacao("04541288000162", _spdata_txt(), _sieg_xlsx("04541288000162"))
    html = client.get(f"/resultado/{st['conciliacao_id']}").text
    assert "/pdf/" in html
    assert "Abrir" in html
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_pdf.py -v` → FAIL (rota inexistente).

- [ ] **Step 3a: Implementar — `app/routers/pdf.py`**
```python
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ConciliacaoItem

router = APIRouter()


@router.get("/pdf/{item_id}")
def ver_pdf(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ConciliacaoItem).filter(ConciliacaoItem.id == item_id).first()
    if not item or not item.arquivo_pdf:
        raise HTTPException(status_code=404, detail="PDF não encontrado")
    conc = item.conciliacao
    if not conc or not conc.pasta_pdfs:
        raise HTTPException(status_code=404, detail="Pasta dos PDFs não registrada")
    base = Path(conc.pasta_pdfs).resolve()
    alvo = (base / item.arquivo_pdf).resolve()
    if not alvo.is_relative_to(base) or not alvo.is_file():
        raise HTTPException(status_code=404,
                            detail="PDF não encontrado — a pasta pode ter sido movida.")
    return FileResponse(str(alvo), media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{item.arquivo_pdf}"'})
```

- [ ] **Step 3b: Implementar — `app/main.py`** (registrar):
```python
from app.routers import processar
from app.routers import pdf
```
```python
app.include_router(processar.router)
app.include_router(pdf.router)
```

- [ ] **Step 3c: Implementar — `app/routers/resultado.py`** (no dict do item dentro de `montar_resumo_e_itens`, acrescentar duas chaves):
```python
        itens.append({
            "id": i.id,
            "numero": pad_numero(i.numero, largura),
            "nome_fornecedor": i.nome_fornecedor, "data_emissao": i.data_emissao,
            "tem_desconto": bool(i.tem_desconto),
            "sieg_bruto": i.valor_bruto, "sieg_liquido": i.valor_liquido,
            "sieg_imp": i.imp_sieg,
            "sp_bruto": i.sp_valor_bruto, "sp_liquido": i.sp_valor_liquido,
            "sp_imp": i.imp_spdata,
            "status_lancamento": i.status_lancamento, "status_arquivo": i.status_arquivo,
            "detalhe": detalhe, "veredito": i.veredito,
            "impostos": json.loads(i.impostos_json) if i.impostos_json else {},
            "arquivo_pdf": i.arquivo_pdf,
        })
```

- [ ] **Step 3d: Implementar — `templates/resultado.html`**:

(i) no cabeçalho da tabela (1ª linha do `<thead>`), inserir a coluna **PDF** entre `Arquivo` e `Divergências`:
```html
        <th rowspan="2">Lançam.</th><th rowspan="2">Arquivo</th>
        <th rowspan="2">PDF</th><th rowspan="2">Divergências</th>
```

(ii) na linha (`<tr>`), depois da célula do `status(i.status_arquivo)` e antes da célula de `detalhe`:
```html
        <td>{{ status(i.status_arquivo) }}</td>
        <td class="center">
          {% if i.arquivo_pdf %}
            <button type="button" class="btn-mini" onclick="verPdf({{ i.id }}, '{{ i.numero }}')">Ver</button>
            <a class="btn-mini" href="/pdf/{{ i.id }}" target="_blank" rel="noopener">Abrir</a>
          {% else %}<span style="color:var(--ink-3)">—</span>{% endif %}
        </td>
        <td style="font-size:12px; color:var(--ink-3)">{{ i.detalhe }}</td>
```

(iii) logo após o `</div>` que fecha `.table-scroll`, adicionar o painel de preview:
```html
<aside id="pdfPanel" class="pdf-panel" style="display:none">
  <div class="pdf-panel-head">
    <span id="pdfTitulo">PDF</span>
    <button type="button" class="btn-mini" onclick="fecharPdf()">Fechar ✕</button>
  </div>
  <iframe id="pdfFrame" title="Pré-visualização do PDF"></iframe>
</aside>
```

(iv) dentro do `<script>` existente (adicionar as funções):
```javascript
  function verPdf(id, numero){
    document.getElementById('pdfTitulo').textContent = 'NF ' + numero;
    document.getElementById('pdfFrame').src = '/pdf/' + id;
    document.getElementById('pdfPanel').style.display = 'flex';
  }
  function fecharPdf(){
    document.getElementById('pdfPanel').style.display = 'none';
    document.getElementById('pdfFrame').src = 'about:blank';
  }
```

- [ ] **Step 3e: Implementar — CSS** (adicionar ao fim de `static/css/syncdata.css`):
```css
td.center{text-align:center; white-space:nowrap}
.btn-mini{display:inline-block; font-size:11.5px; font-weight:600; cursor:pointer;
  border:1px solid var(--line-2); background:var(--surface-2); color:var(--ink-2);
  padding:3px 9px; border-radius:7px; text-decoration:none; margin:0 1px}
.btn-mini:hover{border-color:var(--navy); color:var(--navy)}
.pdf-panel{position:fixed; top:0; right:0; width:min(560px, 46vw); height:100vh;
  background:var(--surface-1); border-left:1px solid var(--line-2);
  box-shadow:-8px 0 24px rgba(0,0,0,.12); display:flex; flex-direction:column; z-index:60}
.pdf-panel-head{display:flex; align-items:center; justify-content:space-between;
  padding:12px 16px; border-bottom:1px solid var(--line-2); font-weight:700; color:var(--navy)}
.pdf-panel iframe{flex:1; width:100%; border:0}
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_pdf.py tests/test_resultado.py -v` → PASS.

- [ ] **Step 5: Rodar a suíte inteira** — `venv/Scripts/python.exe -m pytest -q -W error::DeprecationWarning` → PASS (tudo).

- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: coluna PDF na tela de resultado com preview embutido e abrir em nova aba"`

---

### Task 9: Empacotamento — embutir o Renew no .exe (build adiado)

**Files:**
- Modify: `SyncData.spec`

**Interfaces:**
- Consumes: `renew_runner.localizar_renew_dir()` (frozen → `<_MEIPASS>/renew`).

> **Nota:** esta tarefa **não tem teste automatizado** (é empacotamento). A validação é um **build manual** — que é a etapa de distribuição, **adiada** por decisão do usuário (como na Fase A). O objetivo aqui é deixar o `.spec` pronto para quando o `.exe` for regerado.

- [ ] **Step 1: Implementar — `SyncData.spec`** (acrescentar a distribuição do Renew às `datas`; o resto do arquivo permanece):

No topo, logo após `datas = [('templates', 'templates'), ('static', 'static')]`, trocar por:
```python
import os
_RENEW_DIR = os.environ.get("SYNCDATA_RENEW_DIR", os.path.join('..', 'Renew'))
datas = [('templates', 'templates'), ('static', 'static'), (_RENEW_DIR, 'renew')]
```

- [ ] **Step 2: Commit** — `git add -A && git commit -m "chore: SyncData.spec embute a distribuicao do Renew em _internal/renew"`

- [ ] **Step 3 (manual, adiado — etapa de distribuição):** com a pasta do Renew disponível, gerar e validar o `.exe`:

Build (a partir de uma cópia rasa, ex.: `C:\st`, por causa do MAX_PATH):
```bash
cd "D:/William Lopes - Docs/Documentos/Audiecon/Automocoes/SyncData" && venv/Scripts/pyinstaller.exe SyncData.spec --noconfirm
```
Verificação (smoke): copiar `dist/SyncData` para `C:\SyncData`, rodar `SyncData.exe`, e no navegador: apontar uma pasta com 2–3 PDFs reais → confirmar a barra de progresso, a conciliação, a coluna PDF, o preview e o "Abrir". Confirmar que `_internal/renew/Renew_10.4.exe`, `poppler/`, `tesseract/` e `clientes.txt` foram embutidos.

---

## Self-Review

**1. Cobertura do spec (2026-08-13-fase-b-absorver-renew-design.md):**
- §3 fluxo (2 uploads + pasta, Renew automático) → Task 7. §4 subprocess+progresso → Tasks 5–6. §5 saída→arquivo+PDF → Tasks 1–3. §6 preview+abrir → Task 8. §7 seletor nativo → Task 4. §8 empacotamento → Task 9. §9 erros (pasta inválida/sem PDF/Renew falha) → Tasks 6–7. §10 modelo → Task 3. Coberto.

**2. Placeholders:** nenhum "TBD/TODO"; todo passo tem código real. A única etapa sem teste automatizado (Task 9) é empacotamento, com verificação manual explícita e adiada.

**3. Consistência de tipos/nomes:** `arquivo_pdf` (RegistroRenew→item), `arquivo_row` (ItemConciliacao, setado em `conciliar`, lido em `salvar_conciliacao`), `pasta_pdfs` (Conciliacao, gravado via `nomes["pasta_pdfs"]`), estado do job (`fase/atual/total/conciliacao_id/erro`) — usados igualmente em jobs.py, renew_runner.processar_pasta, processar.py e processando.html. `processar_pasta(job_id, pasta, autorizadas, canceladas, lancamentos, cnpj, nomes=None, runner=None)` — mesma assinatura no runner, na thread do /conciliar e nos helpers de teste. `montar_conciliacao` e `fake_runner` vivem em `tests/_fakes.py` e são usados por Tasks 6–8.

**4. Ordem/verde por tarefa:** o `/conciliar` antigo (upload do Renew) segue funcionando até a Task 7, então os testes da Fase A (test_resultado/test_impostos) ficam verdes nas Tasks 1–6; a Task 7 os migra para `montar_conciliacao` e reescreve test_conciliar. A suíte inteira é validada no fim da Task 8.

## Execution Handoff

Duas opções de execução:

**1. Subagent-Driven (recomendado)** — um subagente por tarefa, revisão entre tarefas, iteração rápida.

**2. Inline Execution** — executa as tarefas nesta sessão com checkpoints.

Qual abordagem?
