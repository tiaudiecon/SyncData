# Ajustes na Conciliação + Impostos (Fase A) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enriquecer a conciliação com bruto/líquido/impostos dos dois lados (Sieg × SPData), busca/filtro, número padronizado, moeda pt-BR, chip de desconto, uma tela nova de Detalhamento de Impostos, e refletir tudo no export `.xlsx`.

**Architecture:** Os impostos vêm de colunas que já existem nos arquivos e hoje são descartadas. Estendemos os parsers para capturá-las, o matcher para carregar o lado SPData casado e abater descontos no confronto, o `ConciliacaoItem` para guardar os dois lados + um `impostos_json`, e as telas/export para exibir. Sem mudança no Renew (Fase B).

**Tech Stack:** Python, FastAPI, Jinja2, SQLAlchemy/SQLite, openpyxl, pytest (já no `venv`).

## Global Constraints

- **Ambiente:** repo `D:\...\Automocoes\SyncData`; o shell reseta o cwd — todo comando Bash começa com `cd "D:/William Lopes - Docs/Documentos/Audiecon/Automocoes/SyncData" && ...`. Branch de trabalho (não `main`). Testes: `venv/Scripts/python.exe -m pytest -q -W error::DeprecationWarning`.
- **Mapeamento de impostos:** ISS = Sieg`ISS` ↔ SPData`ISSQN`; INSS = Sieg`INSS` ↔ SPData`INSS_PJ+INSS_AUTON`; IRRF = Sieg`IR` ↔ SPData`IRPJ+IR_AUTON+IR_COOP`; CSRF = Sieg`PIS+COFINS+CSLL` ↔ SPData`CSRF`.
- **Total retenções Sieg:** `INSS + IR + PIS + COFINS + CSLL + OutRetencoes + (ISS se iss_retido)`. **Total retenções SPData:** `ISSQN + INSS + IR + CSRF`.
- **Descontos:** `descontos = Deducoes + Desconto_Incondic + Desconto_Condic`; confronto usa `bruto_ajustado = Valor_Servico − descontos`. `tem_desconto = descontos > 0,05`.
- **Moeda:** formato pt-BR `R$ 1.234,56` (ponto de milhar, vírgula decimal). No `.xlsx`, célula **numérica** com `number_format = 'R$ #,##0.00'`.
- **Número padronizado:** zeros à esquerda até a largura do maior número da conciliação. Só exibição/export; o **match não muda** (continua com `numero_norm`).
- **Tolerância de valor:** R$ 0,05 (helper `valores_batem` já existe).
- **Banco:** recriado (apagar `syncdata.db`) — pré-produção, sem migração por ALTER.
- **`impostos_json`** (schema fixo em todo o plano):
  `{"sieg": {"iss","inss","ir","csrf","descontos","base_calculo","aliquota","iss_retido","total"}, "spdata": {"iss","inss","ir","csrf","total"} | null}`

---

### Task 1: Parser Sieg — capturar impostos

**Files:**
- Modify: `app/services/parser_sieg.py`
- Test: `tests/test_parser_sieg.py`

**Interfaces:**
- Produces: `NotaSieg` ganha campos `iss, iss_retido(bool), inss, ir, pis, cofins, csll, deducoes, desc_incondic, desc_condic, outret, aliquota, base_calculo` (todos com default) e as propriedades `descontos`, `csrf`, `bruto_ajustado`, `total_retencoes`.

- [ ] **Step 1: Escrever o teste**

Adicionar em `tests/test_parser_sieg.py` (o cabeçalho `HEADERS` do arquivo já tem `Valor_Servico`/`Valor_Liquido`; estender para os impostos):

```python
def test_captura_impostos_e_derivados():
    headers = ["Numero", "Dt_Emissao", "Prestador", "RzPrestador", "Tomador",
               "Valor_Servico", "Valor_Liquido", "IR", "ISS", "ISS_Retido", "CSLL",
               "PIS", "COFINS", "INSS", "Deducoes", "Desconto_Incondic",
               "Desconto_Condic", "OutRetencoes", "Aliquota", "Base_Calculo",
               "Dt_Cancelamento", "Status"]
    import io, openpyxl
    from datetime import datetime
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(headers)
    # F&P: IR 308,70 / CSRF (PIS+COFINS+CSLL) 956,97 / base 20580 / aliq 2 / desc 0
    ws.append(["18", datetime(2026, 7, 17), "30590469000199", "F E P", CLIENTE,
               20580, 19314.33, 308.70, 0, "Não", 308.70, 133.77, 617.40, 0,
               0, 0, 0, 0, 2.0, 20580, None, "Autorizado o uso da NFS-e"])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    aut, _ = ler_sieg(buf, CLIENTE)
    n = aut[0]
    assert n.ir == 308.70
    assert round(n.csrf, 2) == round(308.70 + 133.77 + 617.40, 2)   # CSLL+PIS+COFINS
    assert n.iss_retido is False
    assert n.aliquota == 2.0
    assert n.base_calculo == 20580
    assert n.descontos == 0.0
    assert n.bruto_ajustado == 20580.0
    # total = INSS+IR+PIS+COFINS+CSLL+OutRet + (ISS se retido=False -> 0)
    assert round(n.total_retencoes, 2) == round(308.70 + 308.70 + 133.77 + 617.40, 2)
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_parser_sieg.py::test_captura_impostos_e_derivados -v` → FAIL (campos inexistentes).

- [ ] **Step 3: Implementar** — substituir `parser_sieg.py` por:

```python
from dataclasses import dataclass, field
from datetime import date
from app.services.normalizacao import so_digitos, normalizar_numero_nf, limpar_moeda, para_data
from app.services.planilha import abrir_planilha, mapa_cabecalho, indice, exigir_colunas


@dataclass
class NotaSieg:
    numero: str
    numero_norm: str
    cnpj_prestador: str
    nome_prestador: str
    emissao: "date | None"
    valor_servico: float
    valor_liquido: float
    cancelada: bool
    iss: float = 0.0
    iss_retido: bool = False
    inss: float = 0.0
    ir: float = 0.0
    pis: float = 0.0
    cofins: float = 0.0
    csll: float = 0.0
    deducoes: float = 0.0
    desc_incondic: float = 0.0
    desc_condic: float = 0.0
    outret: float = 0.0
    aliquota: float = 0.0
    base_calculo: float = 0.0

    @property
    def descontos(self) -> float:
        return round(self.deducoes + self.desc_incondic + self.desc_condic, 2)

    @property
    def csrf(self) -> float:
        return round(self.pis + self.cofins + self.csll, 2)

    @property
    def bruto_ajustado(self) -> float:
        return round(self.valor_servico - self.descontos, 2)

    @property
    def total_retencoes(self) -> float:
        iss = self.iss if self.iss_retido else 0.0
        return round(self.inss + self.ir + self.pis + self.cofins + self.csll
                     + self.outret + iss, 2)


def _e_cancelada(dt_cancel, status) -> bool:
    if dt_cancel not in (None, "", "-"):
        return True
    return "cancel" in str(status or "").lower()


def _e_retido(v) -> bool:
    return str(v or "").strip().lower().startswith("s")


def ler_sieg(arquivo, cnpj_cliente: str):
    """Lê o Sieg NFS-e. Mantém só linhas onde Tomador == cnpj_cliente.
    Retorna (autorizadas, canceladas)."""
    alvo = so_digitos(cnpj_cliente)
    headers, linhas = abrir_planilha(arquivo)
    mapa = mapa_cabecalho(headers)

    i_num = indice(mapa, "Numero")
    i_emi = indice(mapa, "Dt_Emissao")
    i_prest = indice(mapa, "Prestador")
    i_nome = indice(mapa, "RzPrestador")
    i_tom = indice(mapa, "Tomador")
    i_serv = indice(mapa, "Valor_Servico")
    i_liq = indice(mapa, "Valor_Liquido")
    i_cancel = indice(mapa, "Dt_Cancelamento")
    i_status = indice(mapa, "Status")
    # impostos (opcionais — se faltarem, ficam 0)
    i_ir = indice(mapa, "IR"); i_iss = indice(mapa, "ISS")
    i_issret = indice(mapa, "ISS_Retido"); i_csll = indice(mapa, "CSLL")
    i_pis = indice(mapa, "PIS"); i_cofins = indice(mapa, "COFINS")
    i_inss = indice(mapa, "INSS"); i_ded = indice(mapa, "Deducoes")
    i_di = indice(mapa, "Desconto_Incondic"); i_dc = indice(mapa, "Desconto_Condic")
    i_out = indice(mapa, "OutRetencoes"); i_aliq = indice(mapa, "Aliquota")
    i_base = indice(mapa, "Base_Calculo")

    exigir_colunas(
        {"Numero": i_num, "Dt_Emissao": i_emi, "Prestador": i_prest,
         "Tomador": i_tom, "Valor_Servico": i_serv, "Valor_Liquido": i_liq},
        lambda nome: (
            f"Planilha do Sieg inválida: não encontrei a coluna '{nome}'. "
            "Confira se o arquivo do Sieg (NFS-e) foi enviado no campo correto."
        ),
    )

    def val(row, i):
        return row[i] if (i is not None and i < len(row)) else None

    def moeda(row, i):
        return limpar_moeda(val(row, i))

    autorizadas, canceladas = [], []
    for row in linhas:
        if not row:
            continue
        if so_digitos(val(row, i_tom)) != alvo:
            continue
        numero = str(val(row, i_num) or "").strip()
        cancelada = _e_cancelada(val(row, i_cancel), val(row, i_status))
        nota = NotaSieg(
            numero=numero,
            numero_norm=normalizar_numero_nf(numero),
            cnpj_prestador=so_digitos(val(row, i_prest)),
            nome_prestador=str(val(row, i_nome) or "").strip(),
            emissao=para_data(val(row, i_emi)),
            valor_servico=moeda(row, i_serv),
            valor_liquido=moeda(row, i_liq),
            cancelada=cancelada,
            iss=moeda(row, i_iss), iss_retido=_e_retido(val(row, i_issret)),
            inss=moeda(row, i_inss), ir=moeda(row, i_ir),
            pis=moeda(row, i_pis), cofins=moeda(row, i_cofins), csll=moeda(row, i_csll),
            deducoes=moeda(row, i_ded), desc_incondic=moeda(row, i_di),
            desc_condic=moeda(row, i_dc), outret=moeda(row, i_out),
            aliquota=moeda(row, i_aliq), base_calculo=moeda(row, i_base),
        )
        (canceladas if cancelada else autorizadas).append(nota)
    return autorizadas, canceladas
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_parser_sieg.py -v` → PASS (todos, incl. os antigos).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: parser Sieg captura impostos (ISS/INSS/IR/PIS/COFINS/CSLL/descontos/base/aliquota)"`

---

### Task 2: Parser SPData — capturar impostos

**Files:**
- Modify: `app/services/parser_spdata.py`
- Test: `tests/test_parser_spdata.py`

**Interfaces:**
- Produces: `LancamentoSpData` ganha campos `issqn, inss_pj, inss_auton, irpj, ir_auton, ir_coop, csrf` (default 0) e as propriedades `inss`, `ir`, `total_retencoes`.

- [ ] **Step 1: Escrever o teste** — em `tests/test_parser_spdata.py` (o `CABECALHO` do arquivo já tem todas as colunas; usar `_linha` só coloca bruto/líquido, então este teste monta uma linha própria com impostos):

```python
def test_captura_impostos_spdata():
    # F&P: IRPJ 308,70 / CSRF 956,97 (a coluna CSRF do SPData)
    cab = ("EMISSAO|ENTRADA|NOTA|CNPJ_CPF|FORNECEDOR|ORIGEM|VALOR_BRUTO|VALOR_LIQUIDO|"
           "IR_COOP|IRPJ|IR_AUTON|CSRF|INSS_PJ|INSS_AUTON|ISSQN|GRUPO|DESC_GRUPO|"
           "SUBGRUPO|DESC_SUBGRUPO|ITEM|DESC_ITEM")
    linha = ("2026-07-17|2026-07-17|18|30590469000199|F E P|GRT|20580.00|19314.33|"
             "0.00|308.70|0.00|956.97|0.00|0.00|0.00|1|G|1|S|1|I")
    conteudo = (cab + "\n" + linha + "\n").encode("cp1252")
    it = ler_spdata(conteudo)[0]
    assert it.irpj == 308.70
    assert it.csrf == 956.97
    assert it.ir == 308.70               # IRPJ+IR_AUTON+IR_COOP
    assert it.inss == 0.0
    assert round(it.total_retencoes, 2) == round(308.70 + 956.97, 2)  # ISSQN+INSS+IR+CSRF
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_parser_spdata.py::test_captura_impostos_spdata -v` → FAIL.

- [ ] **Step 3: Implementar** — substituir `parser_spdata.py` por:

```python
from dataclasses import dataclass
from datetime import date
from app.services.normalizacao import (
    so_digitos, normalizar_numero_nf, limpar_moeda, para_data,
)


@dataclass
class LancamentoSpData:
    numero: str
    numero_norm: str
    cnpj: str
    fornecedor: str
    emissao: "date | None"
    valor_bruto: float
    valor_liquido: float
    issqn: float = 0.0
    inss_pj: float = 0.0
    inss_auton: float = 0.0
    irpj: float = 0.0
    ir_auton: float = 0.0
    ir_coop: float = 0.0
    csrf: float = 0.0

    @property
    def inss(self) -> float:
        return round(self.inss_pj + self.inss_auton, 2)

    @property
    def ir(self) -> float:
        return round(self.irpj + self.ir_auton + self.ir_coop, 2)

    @property
    def total_retencoes(self) -> float:
        return round(self.issqn + self.inss + self.ir + self.csrf, 2)


def ler_spdata(conteudo: bytes) -> "list[LancamentoSpData]":
    """Lê o .txt do SpData (pipe-delimited, Latin-1). Mapeia por NOME de
    coluna no cabeçalho — robusto a mudança de ordem."""
    texto = conteudo.decode("cp1252", errors="replace")
    linhas = [ln for ln in texto.splitlines() if ln.strip()]
    if not linhas:
        return []

    cabecalho = [c.strip().upper() for c in linhas[0].split("|")]
    idx = {nome: i for i, nome in enumerate(cabecalho)}

    for nome in ("NOTA", "CNPJ_CPF", "EMISSAO", "VALOR_BRUTO", "VALOR_LIQUIDO"):
        if nome not in idx:
            raise ValueError(
                f"Arquivo do SpData inválido: não encontrei a coluna '{nome}'. "
                "Confira se o arquivo do SpData foi enviado no campo correto."
            )

    def celula(campos, nome):
        i = idx.get(nome)
        return campos[i].strip() if i is not None and i < len(campos) else ""

    def moeda(campos, nome):
        return limpar_moeda(celula(campos, nome))

    itens = []
    for linha in linhas[1:]:
        campos = linha.split("|")
        numero = celula(campos, "NOTA")
        itens.append(LancamentoSpData(
            numero=numero,
            numero_norm=normalizar_numero_nf(numero),
            cnpj=so_digitos(celula(campos, "CNPJ_CPF")),
            fornecedor=celula(campos, "FORNECEDOR"),
            emissao=para_data(celula(campos, "EMISSAO")),
            valor_bruto=moeda(campos, "VALOR_BRUTO"),
            valor_liquido=moeda(campos, "VALOR_LIQUIDO"),
            issqn=moeda(campos, "ISSQN"),
            inss_pj=moeda(campos, "INSS_PJ"), inss_auton=moeda(campos, "INSS_AUTON"),
            irpj=moeda(campos, "IRPJ"), ir_auton=moeda(campos, "IR_AUTON"),
            ir_coop=moeda(campos, "IR_COOP"), csrf=moeda(campos, "CSRF"),
        ))
    return itens
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_parser_spdata.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: parser SPData captura impostos (ISSQN/INSS/IR/CSRF)"`

---

### Task 3: Formatação — moeda + número padronizado + filtro Jinja

**Files:**
- Create: `app/services/formatacao.py`
- Test: `tests/test_formatacao.py`

**Interfaces:**
- Produces: `moeda(v) -> str` (`"R$ 1.234,56"`); `largura_numeros(numeros) -> int`; `pad_numero(numero, largura) -> str`; `registrar_filtros(templates)` (registra o filtro `moeda`).

- [ ] **Step 1: Escrever o teste `tests/test_formatacao.py`**

```python
from app.services.formatacao import moeda, largura_numeros, pad_numero


def test_moeda_pt_br():
    assert moeda(1234.56) == "R$ 1.234,56"
    assert moeda(800.92) == "R$ 800,92"
    assert moeda(0) == "R$ 0,00"
    assert moeda(1234567.8) == "R$ 1.234.567,80"
    assert moeda(None) == ""


def test_padronizacao_pelo_maior():
    nums = ["18", "2098", "202069"]
    L = largura_numeros(nums)
    assert L == 6
    assert pad_numero("18", L) == "000018"
    assert pad_numero("202069", L) == "202069"
    assert pad_numero("2600000002098", L) == "2600000002098"  # maior que L: inteiro
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_formatacao.py -v` → FAIL.

- [ ] **Step 3: Implementar `app/services/formatacao.py`**

```python
import re


def moeda(v) -> str:
    """Formata número como moeda pt-BR: R$ 1.234,56. '' se não for número."""
    if v is None or v == "":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return ""
    s = f"{n:,.2f}"                    # 1,234.56 (estilo en-US)
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return "R$ " + s


def largura_numeros(numeros) -> int:
    """Maior quantidade de dígitos entre os números (mínimo 1)."""
    larguras = [len(re.sub(r"\D", "", str(n))) for n in numeros if n]
    return max(larguras) if larguras else 1


def pad_numero(numero, largura) -> str:
    """Preenche com zeros à esquerda até `largura` (números maiores ficam inteiros)."""
    d = re.sub(r"\D", "", str(numero or ""))
    if not d:
        return str(numero or "")
    return d.zfill(largura)


def registrar_filtros(templates):
    """Registra o filtro `moeda` no ambiente Jinja dos templates."""
    templates.env.filters["moeda"] = moeda
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_formatacao.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: formatacao (moeda pt-BR + numero padronizado + filtro Jinja)"`

---

### Task 4: Matcher — abater desconto e carregar a linha do SPData

**Files:**
- Modify: `app/services/matcher.py`
- Test: `tests/test_matcher.py`

**Interfaces:**
- Consumes: `NotaSieg.bruto_ajustado` (Task 1).
- Produces: `ItemConciliacao` ganha o campo `lancamento_row=None` (a `LancamentoSpData` casada, ou None). `_avaliar` passa a devolver `(Frente, candidato|None)`.

- [ ] **Step 1: Escrever os testes** — adicionar em `tests/test_matcher.py`:

```python
def test_desconto_nao_gera_divergencia():
    # Sieg bruto 10000, desconto 615 -> ajustado 9385; SPData bruto 9385 -> casa.
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3),
                 10000.0, 9385.0, False, deducoes=615.0)
    l = LancamentoSpData("100", "100", "11111111000111", "F", date(2026, 7, 3),
                         9385.0, 9385.0)
    r = conciliar([n], [], [l], [reg(valor=9385.0)])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_OK
    assert item.veredito == "gerenciada"


def test_item_carrega_linha_spdata_casada():
    r = conciliar([nota()], [], [lanc()], [reg()])
    assert r.itens[0].lancamento_row is not None
    assert r.itens[0].lancamento_row.cnpj == "11111111000111"


def test_faltou_lancar_sem_linha_spdata():
    r = conciliar([nota()], [], [], [reg()])
    assert r.itens[0].lancamento_row is None
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_matcher.py -k "desconto or carrega or sem_linha" -v` → FAIL (`lancamento_row` inexistente).

- [ ] **Step 3: Implementar** — em `app/services/matcher.py`:

(a) `ItemConciliacao` ganha o campo:
```python
@dataclass
class ItemConciliacao:
    nota: object
    lancamento: Frente
    arquivo: Frente
    veredito: str = "pendente"
    lancamento_row: object = None
```

(b) `_avaliar` devolve `(Frente, candidato)` — substituir a função por:
```python
def _avaliar(nota, candidatos_cnpj, comparar):
    """Devolve (Frente, candidato_casado_ou_None)."""
    if not candidatos_cnpj:
        return Frente(STATUS_FALTA, ""), None

    exatos = [c for c in candidatos_cnpj
              if nota.numero_norm and c.numero_norm == nota.numero_norm]
    if exatos:
        melhor = None
        for c in exatos:
            data_ok, valores_ok, detalhe = comparar(nota, c)
            if data_ok and valores_ok:
                return Frente(STATUS_OK, ""), c
            acertos = int(data_ok) + int(valores_ok)
            if melhor is None or acertos > melhor[0]:
                melhor = (acertos, detalhe, c)
        return Frente(STATUS_DIVERG, melhor[1]), melhor[2]

    for c in candidatos_cnpj:
        if _casa_numero(nota.numero_norm, c.numero_norm):
            _, valores_ok, _ = comparar(nota, c)
            if valores_ok:
                return Frente(STATUS_OK, ""), c
    return Frente(STATUS_FALTA, ""), None
```

(c) `_cmp_spdata`/`_cmp_renew` usam `bruto_ajustado` (trocar `nota.valor_servico` por `nota.bruto_ajustado` nas comparações e no texto de divergência):
```python
def _cmp_spdata(nota, c):
    bruto_ok = valores_batem(nota.bruto_ajustado, c.valor_bruto)
    liq_ok = valores_batem(nota.valor_liquido, c.valor_liquido)
    partes = []
    if not bruto_ok:
        partes.append(f"bruto R$ {nota.bruto_ajustado:.2f}≠R$ {c.valor_bruto:.2f}")
    if not liq_ok:
        partes.append(f"líquido R$ {nota.valor_liquido:.2f}≠R$ {c.valor_liquido:.2f}")
    return True, (bruto_ok and liq_ok), "; ".join(partes)


def _cmp_renew(nota, c):
    data_ok = bool(nota.emissao and c.emissao and nota.emissao == c.emissao)
    valor_ok = valores_batem(nota.bruto_ajustado, c.valor)
    partes = []
    if not data_ok:
        partes.append(f"data {_fmt_data(nota.emissao)}≠{_fmt_data(c.emissao)}")
    if not valor_ok:
        partes.append(f"valor R$ {nota.bruto_ajustado:.2f}≠R$ {c.valor:.2f}")
    return data_ok, valor_ok, "; ".join(partes)
```

(d) `conciliar` usa o retorno em tupla:
```python
    for nota in autorizadas:
        lanc, lanc_row = _avaliar(nota, idx_sp.get(nota.cnpj_prestador, []), _cmp_spdata)
        arq, _ = _avaliar(nota, idx_rn.get(nota.cnpj_prestador, []), _cmp_renew)
        veredito = _veredito(lanc, arq)
        res.itens.append(ItemConciliacao(nota, lanc, arq, veredito, lanc_row))
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_matcher.py -v` → PASS (todos, incl. os antigos).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: matcher abate desconto no confronto e carrega a linha SPData casada"`

---

### Task 5: ConciliacaoItem (colunas novas) + persistência (impostos_json)

**Files:**
- Modify: `app/models.py` (classe `ConciliacaoItem`)
- Modify: `app/services/persistencia.py`
- Test: `tests/test_persistencia.py` (novo)

**Interfaces:**
- Consumes: `NotaSieg` (props de impostos), `ItemConciliacao.lancamento_row`.
- Produces: `ConciliacaoItem` com `sp_valor_bruto, sp_valor_liquido, imp_sieg, imp_spdata, tem_desconto, impostos_json`. `salvar_conciliacao` preenche tudo.

- [ ] **Step 1: Escrever o teste `tests/test_persistencia.py`**

```python
import json
from datetime import date
from app.database import Base, engine, SessionLocal
from app.models import Conciliacao, ConciliacaoItem  # noqa
from app.services.parser_sieg import NotaSieg
from app.services.parser_spdata import LancamentoSpData
from app.services.matcher import conciliar
from app.services.persistencia import salvar_conciliacao


def test_persiste_impostos_e_lado_spdata():
    Base.metadata.create_all(bind=engine)
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3), 1000.0, 900.0,
                 False, ir=100.0, iss=0.0, deducoes=0.0)
    l = LancamentoSpData("100", "100", "11111111000111", "F", date(2026, 7, 3),
                         1000.0, 900.0, irpj=100.0)
    from app.services.parser_renew import RegistroRenew
    reg = RegistroRenew("100", "100", "11111111000111", "F", date(2026, 7, 3), 1000.0)
    res = conciliar([n], [], [l], [reg])
    db = SessionLocal()
    conc = salvar_conciliacao(db, "04541288000162",
                              {"spdata": "a", "sieg": "b", "renew": "c"}, res)
    it = db.query(ConciliacaoItem).filter_by(conciliacao_id=conc.id).first()
    assert it.sp_valor_bruto == 1000.0
    assert it.imp_sieg == 100.0 and it.imp_spdata == 100.0
    assert it.tem_desconto is False
    dados = json.loads(it.impostos_json)
    assert dados["sieg"]["ir"] == 100.0
    assert dados["spdata"]["ir"] == 100.0
    db.query(ConciliacaoItem).delete(); db.query(Conciliacao).delete(); db.commit(); db.close()
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_persistencia.py -v` → FAIL.

- [ ] **Step 3a: Implementar — `ConciliacaoItem`** (adicionar as colunas antes de `conciliacao = relationship(...)`):
```python
    sp_valor_bruto = Column(Float, nullable=True)
    sp_valor_liquido = Column(Float, nullable=True)
    imp_sieg = Column(Float, default=0.0)
    imp_spdata = Column(Float, nullable=True)
    tem_desconto = Column(Boolean, default=False)
    impostos_json = Column(String, default="")
```

- [ ] **Step 3b: Implementar — `persistencia.py`** (substituir o arquivo):
```python
import json
from app.models import Conciliacao, ConciliacaoItem


def _fmt_data(d):
    return d.strftime("%d/%m/%Y") if d else ""


def _impostos_json(n, sp):
    dados = {
        "sieg": {"iss": n.iss, "inss": n.inss, "ir": n.ir, "csrf": n.csrf,
                 "descontos": n.descontos, "base_calculo": n.base_calculo,
                 "aliquota": n.aliquota, "iss_retido": n.iss_retido,
                 "total": n.total_retencoes},
        "spdata": ({"iss": sp.issqn, "inss": sp.inss, "ir": sp.ir, "csrf": sp.csrf,
                    "total": sp.total_retencoes} if sp else None),
    }
    return json.dumps(dados)


def salvar_conciliacao(db, cnpj, nomes, resultado):
    """Grava a conciliação (cabeçalho + itens) e devolve o registro."""
    conc = Conciliacao(
        cnpj=cnpj,
        arquivo_spdata_nome=nomes.get("spdata"),
        arquivo_sieg_nome=nomes.get("sieg"),
        arquivo_renew_nome=nomes.get("renew"),
        total_universo=resultado.total_universo,
        valor_total=resultado.valor_total,
        qt_gerenciadas=resultado.qt_gerenciadas,
        qt_ressalva=resultado.qt_ressalva,
        qt_falta_lancar=resultado.qt_falta_lancar,
        qt_falta_arquivar=resultado.qt_falta_arquivar,
        qt_canceladas=resultado.qt_canceladas,
    )
    db.add(conc)
    db.flush()

    for item in resultado.itens:
        n = item.nota
        sp = item.lancamento_row
        db.add(ConciliacaoItem(
            conciliacao_id=conc.id,
            numero=n.numero,
            cnpj_fornecedor=n.cnpj_prestador,
            nome_fornecedor=n.nome_prestador,
            data_emissao=_fmt_data(n.emissao),
            valor_bruto=n.valor_servico,
            valor_liquido=n.valor_liquido,
            sp_valor_bruto=(sp.valor_bruto if sp else None),
            sp_valor_liquido=(sp.valor_liquido if sp else None),
            imp_sieg=n.total_retencoes,
            imp_spdata=(sp.total_retencoes if sp else None),
            tem_desconto=(n.descontos > 0.05),
            impostos_json=_impostos_json(n, sp),
            status_lancamento=item.lancamento.status,
            status_arquivo=item.arquivo.status,
            detalhe_lancamento=item.lancamento.detalhe,
            detalhe_arquivo=item.arquivo.detalhe,
            veredito=item.veredito,
            cancelada=False,
        ))
    db.commit()
    db.refresh(conc)
    return conc
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_persistencia.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: ConciliacaoItem guarda os dois lados + impostos_json"`

---

### Task 6: Resultado router — montar_resumo_e_itens enriquecido

**Files:**
- Modify: `app/routers/resultado.py`
- Test: `tests/test_resultado.py`

**Interfaces:**
- Consumes: `formatacao.largura_numeros/pad_numero/registrar_filtros`, `ConciliacaoItem` (colunas novas + `impostos_json`).
- Produces: `montar_resumo_e_itens(conc)` devolve itens com: `numero` (padronizado), `nome_fornecedor`, `data_emissao`, `tem_desconto`, `sieg_bruto/sieg_liquido/sieg_imp`, `sp_bruto/sp_liquido/sp_imp` (float ou None), `status_lancamento/status_arquivo/detalhe/veredito`, e `impostos` (dict do JSON).

- [ ] **Step 1: Escrever o teste** — adicionar em `tests/test_resultado.py`. Testa a **função** `montar_resumo_e_itens` direto (desacoplado do template, que é a Task 7). Reusa o fluxo /setup + /conciliar e depois carrega a conciliação do banco:

```python
def test_montar_itens_enriquecido(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"), "application/octet-stream"),
        "renew": ("renew.xlsx", _renew_xlsx(), "application/octet-stream"),
    }, follow_redirects=False)
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
    assert it["numero"].isdigit()          # nº padronizado (só dígitos)
```

(Os helpers `_spdata_txt/_sieg_xlsx/_renew_xlsx` já existem em `tests/test_conciliar.py` e são importados no topo de `tests/test_resultado.py`.)

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_resultado.py::test_montar_itens_enriquecido -v` → FAIL (chaves inexistentes).

- [ ] **Step 3: Implementar** — substituir `montar_resumo_e_itens` e registrar o filtro em `app/routers/resultado.py`:

No topo, após `templates = Jinja2Templates(directory="templates")`:
```python
from app.services.formatacao import largura_numeros, pad_numero, registrar_filtros
import json
registrar_filtros(templates)
```

Substituir `montar_resumo_e_itens`:
```python
def montar_resumo_e_itens(conc):
    resumo = {
        "cnpj": conc.cnpj, "data_hora": formatar_dt(conc.data_hora),
        "total_universo": conc.total_universo, "valor_total": conc.valor_total,
        "qt_gerenciadas": conc.qt_gerenciadas, "qt_ressalva": conc.qt_ressalva,
        "qt_falta_lancar": conc.qt_falta_lancar,
        "qt_falta_arquivar": conc.qt_falta_arquivar, "qt_canceladas": conc.qt_canceladas,
    }
    largura = largura_numeros([i.numero for i in conc.itens])
    itens = []
    for i in conc.itens:
        detalhe = "; ".join(d for d in (i.detalhe_lancamento, i.detalhe_arquivo) if d)
        itens.append({
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
        })
    return resumo, itens
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_resultado.py::test_montar_itens_enriquecido -v` → PASS. (O template ainda é o antigo — a Task 7 o reescreve; este teste valida só a função enriquecida, então passa independente do template.)

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: resultado monta valores/impostos dos dois lados + numero padronizado + filtro moeda"`

---

### Task 7: Resultado template — colunas agrupadas + busca/filtro + chip

**Files:**
- Modify: `templates/resultado.html`
- Modify: `static/css/syncdata.css` (estilos de busca/chip/grupo)
- Test: `tests/test_resultado.py` (o mesmo teste da Task 6 agora valida o HTML)

**Interfaces:**
- Consumes: os itens de `montar_resumo_e_itens` (Task 6) e o filtro Jinja `moeda`.

- [ ] **Step 1: Escrever o teste** — adicionar em `tests/test_resultado.py`:
```python
def test_resultado_tem_busca_e_grupos(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    resp = client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"), "application/octet-stream"),
        "renew": ("renew.xlsx", _renew_xlsx(), "application/octet-stream"),
    }, follow_redirects=False)
    html = client.get(resp.headers["location"]).text
    assert 'id="busca"' in html
    assert "Ver impostos" in html
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_resultado.py::test_resultado_tem_busca_e_grupos -v` → FAIL.

- [ ] **Step 3a: Implementar — `templates/resultado.html`** (substituir o arquivo):
```html
{% extends "base.html" %}
{% block titulo %}Resultado · SyncData{% endblock %}
{% block content %}
{% macro status(s) %}
  {%- if s == 'ok' -%}<span class="badge b-ok">OK</span>
  {%- elif s == 'diverg' -%}<span class="badge b-warn">Divergência</span>
  {%- else -%}<span class="badge b-alert">Faltou</span>{%- endif -%}
{% endmacro %}
<div class="page-head">
  <div><div class="crumb">Resultado · {{ resumo.data_hora }}</div><h1>Conciliação</h1></div>
  <div class="actions">
    <a class="btn btn-ghost" href="/impostos/{{ c.id }}">Ver impostos</a>
    <a class="btn btn-primary" href="/resultado/{{ c.id }}/planilha.xlsx">
      <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Exportar .xlsx</a>
  </div>
</div>

<div class="kpi-row">
  <div class="kpi hl"><div class="lbl">Universo</div><div class="val tnum">{{ resumo.total_universo }}</div></div>
  <div class="kpi ok"><div class="lbl">Gerenciadas</div><div class="val tnum">{{ resumo.qt_gerenciadas }}</div></div>
  <div class="kpi warn"><div class="lbl">Com ressalva</div><div class="val tnum">{{ resumo.qt_ressalva }}</div></div>
  <div class="kpi alert"><div class="lbl">Faltou lançar</div><div class="val tnum">{{ resumo.qt_falta_lancar }}</div></div>
  <div class="kpi alert"><div class="lbl">Faltou arquivar</div><div class="val tnum">{{ resumo.qt_falta_arquivar }}</div></div>
</div>

<div class="toolbar">
  <input id="busca" class="input" style="max-width:320px" placeholder="Buscar por nº, fornecedor ou valor…" oninput="filtrar()">
  <div class="chips">
    <button class="chip on" data-f="todas" onclick="setFiltro(this)">Todas</button>
    <button class="chip" data-f="gerenciada" onclick="setFiltro(this)">Gerenciadas</button>
    <button class="chip" data-f="ressalva" onclick="setFiltro(this)">Ressalva</button>
    <button class="chip" data-f="pendente" onclick="setFiltro(this)">Pendentes</button>
  </div>
</div>

<div class="table-scroll">
  <table class="dense" id="tab">
    <thead>
      <tr>
        <th rowspan="2">Nº NF</th><th rowspan="2">Fornecedor</th><th rowspan="2">Emissão</th>
        <th colspan="3" class="grp">Sieg</th><th colspan="3" class="grp">SPData</th>
        <th rowspan="2">Lançam.</th><th rowspan="2">Arquivo</th><th rowspan="2">Divergências</th>
      </tr>
      <tr><th class="right">Bruto</th><th class="right">Líq</th><th class="right">Imp</th>
          <th class="right">Bruto</th><th class="right">Líq</th><th class="right">Imp</th></tr>
    </thead>
    <tbody>
    {% for i in itens %}
      <tr data-v="{{ i.veredito }}" data-busca="{{ (i.numero ~ ' ' ~ i.nome_fornecedor ~ ' ' ~ i.sieg_bruto)|lower }}">
        <td class="bold mono">{{ i.numero }}</td>
        <td>{{ i.nome_fornecedor }}{% if i.tem_desconto %} <span class="chip-desc">• desc</span>{% endif %}</td>
        <td class="mono">{{ i.data_emissao }}</td>
        <td class="mono right">{{ i.sieg_bruto|moeda }}</td>
        <td class="mono right">{{ i.sieg_liquido|moeda }}</td>
        <td class="mono right">{{ i.sieg_imp|moeda }}</td>
        <td class="mono right">{{ i.sp_bruto|moeda if i.sp_bruto is not none else '—' }}</td>
        <td class="mono right">{{ i.sp_liquido|moeda if i.sp_liquido is not none else '—' }}</td>
        <td class="mono right">{{ i.sp_imp|moeda if i.sp_imp is not none else '—' }}</td>
        <td>{{ status(i.status_lancamento) }}</td>
        <td>{{ status(i.status_arquivo) }}</td>
        <td style="font-size:12px; color:var(--ink-3)">{{ i.detalhe }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<script>
  let filtroStatus = 'todas';
  function setFiltro(btn){
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('on'));
    btn.classList.add('on'); filtroStatus = btn.dataset.f; filtrar();
  }
  function filtrar(){
    const q = (document.getElementById('busca').value || '').toLowerCase();
    document.querySelectorAll('#tab tbody tr').forEach(tr => {
      const okStatus = filtroStatus === 'todas' || tr.dataset.v === filtroStatus;
      const okBusca = !q || (tr.dataset.busca || '').includes(q);
      tr.style.display = (okStatus && okBusca) ? '' : 'none';
    });
  }
</script>
{% endblock %}
```

- [ ] **Step 3b: Implementar — CSS** (adicionar ao fim de `static/css/syncdata.css`):
```css
.toolbar{display:flex; align-items:center; gap:14px; margin:0 0 16px; flex-wrap:wrap}
.chips{display:flex; gap:6px; flex-wrap:wrap}
.chip{border:1px solid var(--line-2); background:var(--surface-2); color:var(--ink-2);
  padding:6px 13px; border-radius:999px; font-size:12.5px; font-weight:600; cursor:pointer}
.chip:hover{border-color:var(--ink-3)}
.chip.on{background:var(--navy); color:var(--creme); border-color:var(--navy)}
.chip-desc{display:inline-block; font-size:10px; font-weight:700; color:var(--burdo);
  background:var(--burdo-100); padding:1px 6px; border-radius:999px; vertical-align:middle}
table.dense th.grp{text-align:center; background:var(--navy); color:var(--creme)}
```

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_resultado.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: tela de resultado com colunas agrupadas Sieg|SPData, busca/filtro e chip de desconto"`

---

### Task 8: Detalhamento de Impostos — router + template + menu

**Files:**
- Create: `app/routers/impostos.py`, `templates/impostos.html`
- Modify: `app/main.py` (incluir o router), `templates/base.html` (item de menu)
- Test: `tests/test_impostos.py` (novo)

**Interfaces:**
- Consumes: `ConciliacaoItem.impostos_json`, `formatacao.registrar_filtros`, `contexto_cliente`, `formatar_dt`.
- Produces: `GET /impostos` (mais recente), `GET /impostos/{id}`.

- [ ] **Step 1: Escrever o teste `tests/test_impostos.py`** (reusa a fixture `client` do conftest e os helpers de `test_conciliar`):
```python
from tests.test_conciliar import _sieg_xlsx, _renew_xlsx, _spdata_txt


def test_impostos_renderiza(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    client.post("/conciliar", files={
        "spdata": ("SpData.txt", _spdata_txt(), "text/plain"),
        "sieg": ("sieg.xlsx", _sieg_xlsx("04541288000162"), "application/octet-stream"),
        "renew": ("renew.xlsx", _renew_xlsx(), "application/octet-stream"),
    }, follow_redirects=False)
    r = client.get("/impostos")           # a mais recente
    assert r.status_code == 200
    assert "Detalhamento de Impostos" in r.text
    assert "CSRF" in r.text


def test_impostos_vazio_sem_conciliacao(client):
    client.post("/setup", data={"cnpj": "04541288000162", "razao_social": "HSS"})
    r = client.get("/impostos")
    assert r.status_code == 200
    assert "Nenhuma conciliação" in r.text
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_impostos.py -v` → FAIL (rota inexistente).

- [ ] **Step 3a: Implementar — `app/routers/impostos.py`**
```python
import json
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Conciliacao
from app.services.tempo import formatar_dt
from app.services.configuracao import contexto_cliente
from app.services.formatacao import registrar_filtros, largura_numeros, pad_numero

router = APIRouter()
templates = Jinja2Templates(directory="templates")
registrar_filtros(templates)

_TOL = 0.05


def _delta(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 2)


def _linhas(conc):
    largura = largura_numeros([i.numero for i in conc.itens])
    linhas = []
    for i in conc.itens:
        dados = json.loads(i.impostos_json) if i.impostos_json else {}
        s = dados.get("sieg") or {}
        p = dados.get("spdata")
        def par(chave):
            sv = s.get(chave, 0.0)
            pv = (p or {}).get(chave) if p else None
            return {"sieg": sv, "sp": pv, "delta": _delta(sv, pv)}
        linhas.append({
            "numero": pad_numero(i.numero, largura), "nome": i.nome_fornecedor,
            "iss": par("iss"), "inss": par("inss"), "ir": par("ir"), "csrf": par("csrf"),
            "total": par("total"),
            "descontos": s.get("descontos", 0.0), "base": s.get("base_calculo", 0.0),
            "aliquota": s.get("aliquota", 0.0),
        })
    return linhas


def _diverge(linha):
    for k in ("iss", "inss", "ir", "csrf", "total"):
        d = linha[k]["delta"]
        if d is not None and abs(d) > _TOL:
            return True
    return False


@router.get("/impostos")
def mais_recente(request: Request, db: Session = Depends(get_db)):
    conc = db.query(Conciliacao).order_by(Conciliacao.data_hora.desc()).first()
    return _render(request, db, conc)


@router.get("/impostos/{conciliacao_id}")
def por_id(conciliacao_id: int, request: Request, db: Session = Depends(get_db)):
    conc = db.query(Conciliacao).filter(Conciliacao.id == conciliacao_id).first()
    if not conc:
        raise HTTPException(status_code=404, detail="Conciliação não encontrada")
    return _render(request, db, conc)


def _render(request, db, conc):
    linhas = _linhas(conc) if conc else []
    for l in linhas:
        l["diverge"] = _diverge(l)
    return templates.TemplateResponse(request, "impostos.html", {
        "ativo": "impostos", "conc": conc,
        "data_hora": formatar_dt(conc.data_hora) if conc else "",
        "linhas": linhas, **contexto_cliente(db),
    })
```

- [ ] **Step 3b: Implementar — `templates/impostos.html`**
```html
{% extends "base.html" %}
{% block titulo %}Impostos · SyncData{% endblock %}
{% block content %}
{% macro cel(p) %}
  {%- if p.sp is none -%}<td class="mono right">{{ p.sieg|moeda }}</td><td class="mono right">—</td><td class="right">—</td>
  {%- else -%}<td class="mono right">{{ p.sieg|moeda }}</td><td class="mono right">{{ p.sp|moeda }}</td>
    <td class="mono right {% if p.delta and (p.delta > 0.05 or p.delta < -0.05) %}dz{% endif %}">{{ p.delta|moeda }}</td>{%- endif -%}
{% endmacro %}
<div class="page-head">
  <div><div class="crumb">{% if conc %}Conciliação · {{ data_hora }}{% endif %}</div><h1>Detalhamento de Impostos</h1></div>
  {% if conc %}<div class="actions"><a class="btn btn-ghost" href="/resultado/{{ conc.id }}">Voltar ao resultado</a></div>{% endif %}
</div>

{% if not conc %}
  <div class="panel"><div class="empty">Nenhuma conciliação ainda. Vá em <strong>Conciliar</strong> para começar.</div></div>
{% else %}
<div class="toolbar">
  <label class="chip on" id="chDiv"><input type="checkbox" onchange="soDiverg(this)" style="margin-right:6px">Só divergências</label>
</div>
<div class="table-scroll">
  <table class="dense" id="tab">
    <thead>
      <tr>
        <th rowspan="2">Nº</th><th rowspan="2">Fornecedor</th>
        <th colspan="3" class="grp">ISS</th><th colspan="3" class="grp">INSS</th>
        <th colspan="3" class="grp">IRRF</th><th colspan="3" class="grp">CSRF</th>
        <th rowspan="2" class="right">Descontos</th><th rowspan="2" class="right">Base Cálc.</th>
        <th rowspan="2" class="right">Alíq.</th>
        <th colspan="3" class="grp">Total ret.</th>
      </tr>
      <tr>
        {% for _ in range(5) %}<th class="right">Sieg</th><th class="right">SP</th><th class="right">Δ</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
    {% for l in linhas %}
      <tr data-div="{{ '1' if l.diverge else '0' }}">
        <td class="bold mono">{{ l.numero }}</td><td>{{ l.nome }}</td>
        {{ cel(l.iss) }}{{ cel(l.inss) }}{{ cel(l.ir) }}{{ cel(l.csrf) }}
        <td class="mono right">{{ l.descontos|moeda }}</td>
        <td class="mono right">{{ l.base|moeda }}</td>
        <td class="mono right">{{ '%.2f'|format(l.aliquota) }}</td>
        {{ cel(l.total) }}
      </tr>
    {% endfor %}
    </tbody>
  </table>
</div>
<script>
  function soDiverg(chk){
    document.querySelectorAll('#tab tbody tr').forEach(tr => {
      tr.style.display = (!chk.checked || tr.dataset.div === '1') ? '' : 'none';
    });
  }
</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 3c: Implementar — CSS** (adicionar em `static/css/syncdata.css`): `.dz{color:var(--alert); font-weight:700}`

- [ ] **Step 3d: Implementar — menu** em `templates/base.html`: adicionar, logo após o item "Conciliar" (antes de "Histórico"):
```html
      <a href="/impostos" class="sb-item {% if ativo == 'impostos' %}active{% endif %}">
        <svg viewBox="0 0 24 24"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        Impostos
      </a>
```

- [ ] **Step 3e: Implementar — `app/main.py`**: `from app.routers import impostos` e `app.include_router(impostos.router)`.

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_impostos.py -v` → PASS.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: tela Detalhamento de Impostos (menu + rota + comparacao Sieg/SP/delta)"`

---

### Task 9: Export `.xlsx` — colunas novas + aba Impostos + moeda numérica

**Files:**
- Modify: `app/services/exportacao.py`
- Test: `tests/test_exportacao.py`

**Interfaces:**
- Consumes: itens de `montar_resumo_e_itens` (Task 6) com `sieg_*`, `sp_*`, `tem_desconto`, `impostos`.

- [ ] **Step 1: Escrever o teste** — em `tests/test_exportacao.py`, estender `_itens()` para incluir os campos novos e adicionar:
```python
def _itens_ricos():
    base = _itens()
    for it in base:
        it.update({"sieg_bruto": it["valor_bruto"], "sieg_liquido": it["valor_liquido"],
                   "sieg_imp": 0.0, "sp_bruto": it["valor_bruto"],
                   "sp_liquido": it["valor_liquido"], "sp_imp": 0.0, "tem_desconto": False,
                   "impostos": {"sieg": {"iss":0,"inss":0,"ir":0,"csrf":0,"descontos":0,
                                "base_calculo":0,"aliquota":0,"iss_retido":False,"total":0},
                                "spdata": {"iss":0,"inss":0,"ir":0,"csrf":0,"total":0}}})
    return base


def test_export_tem_aba_impostos_e_moeda_numerica():
    import io, openpyxl
    conteudo = gerar_xlsx(_resumo(), _itens_ricos())
    wb = openpyxl.load_workbook(io.BytesIO(conteudo))
    assert "Impostos" in wb.sheetnames
    ws = wb["Conciliação"]
    # acha uma célula de valor (Bruto Sieg) e confirma que é número com formato moeda
    achou = False
    for row in ws.iter_rows():
        for cel in row:
            if isinstance(cel.value, (int, float)) and "R$" in (cel.number_format or ""):
                achou = True
    assert achou
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_exportacao.py::test_export_tem_aba_impostos_e_moeda_numerica -v` → FAIL.

- [ ] **Step 3: Implementar** — em `app/services/exportacao.py`:

(a) constante de formato e cabeçalhos novos (substituir `CABECALHOS` e `_linha_item`):
```python
_MOEDA = 'R$ #,##0.00'
CABECALHOS = ["Nº NF", "Fornecedor", "Emissão",
              "Bruto (Sieg)", "Líq (Sieg)", "Imp (Sieg)",
              "Bruto (SPData)", "Líq (SPData)", "Imp (SPData)",
              "Desc?", "Lançamento", "Arquivo", "Divergências", "Veredito"]
_COLS_MOEDA = (4, 5, 6, 7, 8, 9)          # 1-based: as 6 colunas de valor
_COL_STATUS = (11, 12)                     # Lançamento, Arquivo


def _linha_item(it):
    return [it["numero"], it["nome_fornecedor"], it["data_emissao"],
            it.get("sieg_bruto", 0.0), it.get("sieg_liquido", 0.0), it.get("sieg_imp", 0.0),
            it.get("sp_bruto"), it.get("sp_liquido"), it.get("sp_imp"),
            "Sim" if it.get("tem_desconto") else "",
            _ROTULO_STATUS.get(it["status_lancamento"], it["status_lancamento"]),
            _ROTULO_STATUS.get(it["status_arquivo"], it["status_arquivo"]),
            it.get("detalhe", ""), it["veredito"].capitalize()]
```

(b) em `_escrever_aba`, ao gravar a linha, aplicar formato moeda nas colunas de valor e cor de status nas novas posições — substituir o laço de escrita das linhas por:
```python
    linhas = [_linha_item(it) for it in itens]
    for offset, (it, linha) in enumerate(zip(itens, linhas)):
        r = primeira_dado + offset
        for c, valor in enumerate(linha, start=1):
            cel = ws.cell(r, c, valor)
            cel.font = _FONTE_DADO
            cel.border = _BORDA
            if offset % 2 == 1:
                cel.fill = _FILL_ZEBRA
            if c in _COLS_MOEDA and isinstance(valor, (int, float)):
                cel.number_format = _MOEDA
        for col, chave in ((_COL_STATUS[0], it["status_lancamento"]),
                           (_COL_STATUS[1], it["status_arquivo"])):
            fill, fonte = _FILL_STATUS.get(chave, (None, _FONTE_DADO))
            if fill:
                ws.cell(r, col).fill = fill
                ws.cell(r, col).font = fonte
    _largura(ws, CABECALHOS, [[""] * len(CABECALHOS)] + linhas)
```

(c) nova aba Impostos — adicionar a função e chamá-la em `gerar_xlsx`:
```python
CAB_IMP = ["Nº NF", "Fornecedor",
           "ISS Sieg", "ISS SP", "INSS Sieg", "INSS SP", "IRRF Sieg", "IRRF SP",
           "CSRF Sieg", "CSRF SP", "Descontos", "Base Cálc.", "Alíquota",
           "Total Sieg", "Total SP"]


def _aba_impostos(ws, itens):
    for c, t in enumerate(CAB_IMP, start=1):
        cel = ws.cell(1, c, t); cel.font = _FONTE_CAB; cel.fill = _FILL_CAB; cel.alignment = _CENTRO
    ws.freeze_panes = "A2"
    for off, it in enumerate(itens):
        s = (it.get("impostos") or {}).get("sieg") or {}
        p = (it.get("impostos") or {}).get("spdata") or {}
        vals = [it["numero"], it["nome_fornecedor"],
                s.get("iss", 0), p.get("iss"), s.get("inss", 0), p.get("inss"),
                s.get("ir", 0), p.get("ir"), s.get("csrf", 0), p.get("csrf"),
                s.get("descontos", 0), s.get("base_calculo", 0), s.get("aliquota", 0),
                s.get("total", 0), p.get("total")]
        r = 2 + off
        for c, v in enumerate(vals, start=1):
            cel = ws.cell(r, c, v); cel.font = _FONTE_DADO; cel.border = _BORDA
            if off % 2 == 1:
                cel.fill = _FILL_ZEBRA
            if c >= 3 and c != 13 and isinstance(v, (int, float)):   # 13 = Alíquota (não é moeda)
                cel.number_format = _MOEDA
    _largura(ws, CAB_IMP, [[c] for c in CAB_IMP])
```

Em `gerar_xlsx`, antes do `buf = io.BytesIO()`:
```python
    _aba_impostos(wb.create_sheet("Impostos"), itens)
```
E trocar o texto do total: `("Valor total (bruto)", resumo["valor_total"])` pode receber `cel.number_format = _MOEDA` — opcional; manter como está é aceitável.

- [ ] **Step 4: Rodar (passa)** — `venv/Scripts/python.exe -m pytest tests/test_exportacao.py -v` → PASS (todos, incl. os antigos que checam as 3 abas — agora são 4: Conciliação, Faltou Lançar, Faltou Arquivar, Impostos; ajustar o assert antigo `wb.sheetnames == [...]` para incluir "Impostos" no fim, ou usar `set(...) >= {...}`).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: export .xlsx com valores/impostos dos dois lados (moeda numerica) + aba Impostos"`

---

## Self-Review (preenchido)

**Cobertura do spec:**
- Impostos capturados (Sieg/SPData) → Tasks 1, 2. Mapeamento e totais → props em 1/2 + `_impostos_json` em 5.
- Descontos abatidos → Task 4; chip `• desc` → Task 7; detalhe → Tasks 8, 9.
- Moeda + nº padronizado → Task 3, usados em 6/7/9.
- Colunas agrupadas Sieg|SPData + busca/filtro → Tasks 6, 7.
- Tela Detalhamento (menu + Base/Alíquota + Δ + totais) → Task 8.
- Export enriquecido + aba Impostos → Task 9.
- Banco recriado (sem migração) → nota nos Global Constraints (apagar `syncdata.db`).

**Placeholders:** nenhum passo sem código; os TODO de "ajustar assert antigo" (Tasks 6, 9) trazem a instrução exata do que mudar.

**Consistência de tipos/nomes:** `NotaSieg.bruto_ajustado/total_retencoes/csrf/descontos`; `LancamentoSpData.inss/ir/total_retencoes`; `ItemConciliacao.lancamento_row`; `_avaliar -> (Frente, cand)`; `impostos_json` schema `{sieg{...}, spdata{...}|null}`; itens de `montar_resumo_e_itens` com chaves `sieg_*/sp_*/tem_desconto/impostos` consumidas igual em 7 e 9. Filtro Jinja `moeda` registrado via `registrar_filtros` em `resultado.py` e `impostos.py`.

## Notas de execução
- As Tasks 1 e 2 mudam os dataclasses (campos novos **com default**, após os campos sem
  default) — os helpers `nota()/lanc()/reg()` dos testes existentes continuam válidos
  (chamada posicional dos campos antigos).
- Tasks que ajustam asserts antigos: **Task 9** (`sheetnames` agora inclui "Impostos").
- Ao final, apagar `syncdata.db` local (schema novo) e rodar a suíte inteira:
  `venv/Scripts/python.exe -m pytest -q -W error::DeprecationWarning`.
