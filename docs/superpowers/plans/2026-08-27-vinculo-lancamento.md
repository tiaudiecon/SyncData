# Vínculo manual de lançamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que o operador **vincule manualmente** uma nota do Sieg em erro ("faltou lançar") a um lançamento da lista "SP sem SIEG" (mesmo CNPJ+valor, número da nota errado/0), reconectando os dois órfãos sem afrouxar o match automático.

**Architecture:** Nova tratativa "Vinculada" espelhando o padrão Aceite/Validação (modelo → serviço → router → `montar_resumo_e_itens` → template/CSS → exportação → pacote/import → testes), com DUAS diferenças em relação ao Aceite: (1) o registro guarda a **identidade do lançamento-alvo** (sp_cnpj+sp_numero+sp_valor), não só uma observação; (2) na exibição, o vínculo **consome** o item `sp_sem_sieg` casado e **roda a comparação de valores** (bruto/líquido/impostos) para decidir Gerenciada×Ressalva. Construído nas DUAS versões (v1 SyncData / v2 SyncDataServer).

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2.0 (v1 SQLite / v2 Postgres+pg8000), openpyxl, pytest. Design "Moderatio".

**Spec:** `docs/superpowers/specs/2026-08-27-vinculo-lancamento-design.md` (aprovado).

## Global Constraints

- **Selo/tag:** texto **"Vinculada"**; cor **teal** — `--teal:#0E7C86; --teal-bg:#DCF0EE;` (CSS) e `_TEAL="FF0E7C86"` / fill `"FFDCF0EE"` (Excel). Distinta de verde/azul/roxo/amarelo já usados.
- **Escopo:** por **nota + competência** (v2 também por `empresa_id`). Reversível.
- **Rotas:** `POST /vinculos/marcar` e `POST /vinculos/desfazer` (v2: com `empresa_id` no form + `conferir_empresa`).
- **Chave lógica do mapa** (igual ao aceite): `(cnpj_norm, numero_norm)` da **nota do Sieg** → valor rico `{sp_cnpj, sp_numero, sp_valor, obs}`.
- **Fronteira:** resolve só o lado do **lançamento (SpData)**. NÃO tocar no lado do arquivo/Renew.
- **Efeito:** vincular → comparar valores → Gerenciada (bate) ou Ressalva (diverge). O lançamento vinculado sai de "SP sem SIEG". Ortogonal ao Aceite (Ressalva pós-vínculo ainda pode ser Aceita).
- **Sem migração manual:** tabela nova nasce por `Base.metadata.create_all` (v1 `app/main.py`; v2 idem). NÃO editar `migracao.py`.
- **Rótulos de auditoria (v2):** `"lancamento_vinculado": "Lançamento vinculado"`, `"vinculo_desfeito": "Vínculo desfeito"`.
- **Candidatos do seletor:** montados no template a partir dos itens `sp_sem_sieg` já presentes em `itens` (mesmo CNPJ por padrão, "ver todas" amplia) — NÃO criar rota/serviço de busca.
- **TDD** em toda tarefa: teste falha → implementa → passa. Rodar com `venv/Scripts/python.exe -m pytest`. Baseline: v1 = 155 testes; v2 = 235 testes.

---

## File Structure

**v1 — `D:\William Lopes - Docs\Documentos\Audiecon\Automocoes\SyncData`**
- Modify `app/models.py` — nova classe `Vinculo`.
- Create `app/services/vinculos.py` — `mapa/salvar/remover`.
- Create `app/routers/vinculos.py` — `/vinculos/marcar` + `/vinculos/desfazer`.
- Modify `app/main.py` — import + `include_router`.
- Modify `app/routers/resultado.py` — `montar_resumo_e_itens` (param `vinculos`, pós-passo de vínculo, contagens) + `_resumo_itens`.
- Modify `templates/resultado.html` — chip, `data-vinculo`, selo, seletor+form, JS do filtro.
- Modify `static/css/syncdata.css` — vars teal + `.b-teal` + `.btn-mini.b-teal-btn`.
- Modify `app/services/exportacao.py` — situação/estilo/resumo/guia "Vinculadas".
- Modify `app/services/pacote_dados.py` — item `vinculo` + resumo `vinculadas`.
- Create `tests/test_vinculos.py`; Modify `tests/conftest.py` (limpar tabela nova).

**v2 — `D:\William Lopes - Docs\Documentos\Audiecon\Automocoes\SyncDataServer`** (espelho + multi-empresa)
- Mesmos arquivos + `app/routers/_escopo.py` (usar `conferir_empresa`), `app/services/auditoria.py` (2 rótulos), `app/services/importacao.py` (reconstruir vínculo), `tests/conftest.py` (`_limpar_tabelas`), `tests/test_v2_vinculos.py`.

---

# PARTE A — v1 (SyncData)

### Task A1: Modelo `Vinculo` + serviço + router + registro

**Files:**
- Modify: `app/models.py` (após a classe `AceiteDivergencia`, ~linha 133)
- Create: `app/services/vinculos.py`
- Create: `app/routers/vinculos.py`
- Modify: `app/main.py` (import ~19, include_router ~74)
- Test: `tests/test_vinculos.py`

**Interfaces produzidas:**
- `Vinculo(Base)` colunas: `id, competencia, cnpj, numero, sp_cnpj, sp_numero, sp_valor(Float), nome, observacao, criado_em`; unique `(competencia, cnpj, numero)`.
- `vinculos.mapa(db, competencia) -> {(cnpj_norm, numero_norm): {"sp_cnpj","sp_numero","sp_valor","obs"}}`
- `vinculos.salvar(db, competencia, cnpj, numero, nome, sp_cnpj, sp_numero, sp_valor, observacao) -> Vinculo|None`
- `vinculos.remover(db, competencia, cnpj, numero) -> bool`

- [ ] **Step 1: Teste do serviço (falha)** — `tests/test_vinculos.py`, copiando o estilo de `tests/test_aceites.py`:

```python
from app.database import SessionLocal, engine, Base
from app.models import Conciliacao, ConciliacaoItem
from app.services import vinculos as serv


def test_service_mapa_salvar_remover():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 970.0, "num errado no spdata")
    m = serv.mapa(db, "2026-07")
    v = m[("54017315000170", "300")]
    assert v["sp_numero"] == "0" and v["sp_valor"] == 970.0 and "errado" in v["obs"]
    assert serv.mapa(db, "2026-08") == {}                 # isolado por competência
    assert serv.remover(db, "2026-07", "54017315000170", "300") is True
    assert serv.mapa(db, "2026-07") == {}
    db.close()
```

- [ ] **Step 2: Rodar (falha)** — `venv/Scripts/python.exe -m pytest tests/test_vinculos.py -q` → ImportError/No module.

- [ ] **Step 3: Modelo** — em `app/models.py`, após `AceiteDivergencia`:

```python
class Vinculo(Base):
    """Vínculo manual: liga uma nota do Sieg em erro ('faltou lançar') a um
    lançamento da lista 'SP sem SIEG' (número da NF errado/0). Guarda a identidade
    do lançamento-alvo (sp_*). Vale só na competência (como a Validação/Aceite)."""
    __tablename__ = "vinculo_lancamento"
    __table_args__ = (UniqueConstraint("competencia", "cnpj", "numero",
                                       name="uq_vinculo_comp_cnpj_num"),)
    id = Column(Integer, primary_key=True)
    competencia = Column(String, nullable=False, index=True)
    cnpj = Column(String, nullable=False)          # CNPJ da NOTA do Sieg
    numero = Column(String, nullable=False)        # número da NOTA do Sieg
    sp_cnpj = Column(String, nullable=False)       # CNPJ do lançamento SP escolhido
    sp_numero = Column(String, nullable=False, default="")   # número no SpData (pode ser "0"/"")
    sp_valor = Column(Float, nullable=False, default=0.0)    # bruto do SpData (desempate)
    nome = Column(String)
    observacao = Column(String, nullable=False, default="")
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

(Confirmar imports já presentes: `Float`, `UniqueConstraint`, `datetime`, `timezone` — em `app/models.py:1-5`.)

- [ ] **Step 4: Serviço** — `app/services/vinculos.py` (espelho de `aceites.py`, com os campos sp_*):

```python
from app.models import Vinculo
from app.services.normalizacao import so_digitos


def mapa(db, competencia):
    """{(cnpj_norm, numero_norm) da NOTA: {sp_cnpj, sp_numero, sp_valor, obs}}."""
    if not competencia:
        return {}
    linhas = db.query(Vinculo).filter(Vinculo.competencia == competencia).all()
    return {(so_digitos(v.cnpj), so_digitos(v.numero)): {
        "sp_cnpj": so_digitos(v.sp_cnpj), "sp_numero": so_digitos(v.sp_numero),
        "sp_valor": v.sp_valor, "obs": v.observacao or ""} for v in linhas}


def salvar(db, competencia, cnpj, numero, nome, sp_cnpj, sp_numero, sp_valor, observacao):
    cn, nn = so_digitos(cnpj), so_digitos(numero)
    if not (competencia and cn and nn):
        return None
    v = (db.query(Vinculo).filter(Vinculo.competencia == competencia,
                                  Vinculo.cnpj == cn, Vinculo.numero == nn).first())
    if v:
        v.sp_cnpj, v.sp_numero, v.sp_valor = so_digitos(sp_cnpj), so_digitos(sp_numero), float(sp_valor or 0.0)
        v.observacao = observacao or ""
        if nome:
            v.nome = nome
    else:
        v = Vinculo(competencia=competencia, cnpj=cn, numero=nn,
                    sp_cnpj=so_digitos(sp_cnpj), sp_numero=so_digitos(sp_numero),
                    sp_valor=float(sp_valor or 0.0), nome=nome or "", observacao=observacao or "")
        db.add(v)
    db.commit()
    return v


def remover(db, competencia, cnpj, numero):
    cn, nn = so_digitos(cnpj), so_digitos(numero)
    v = (db.query(Vinculo).filter(Vinculo.competencia == competencia,
                                  Vinculo.cnpj == cn, Vinculo.numero == nn).first())
    if v:
        db.delete(v); db.commit(); return True
    return False
```

- [ ] **Step 5: Router** — `app/routers/vinculos.py` (espelho de `aceites.py`, com os campos sp_*):

```python
from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import vinculos as serv

router = APIRouter()


@router.post("/vinculos/marcar")
def marcar(cnpj: str = Form(...), numero: str = Form(...), nome: str = Form(""),
           sp_cnpj: str = Form(...), sp_numero: str = Form(""), sp_valor: float = Form(0.0),
           observacao: str = Form(...), competencia: str = Form(...),
           conciliacao_id: int = Form(...), db: Session = Depends(get_db)):
    serv.salvar(db, competencia.strip(), cnpj, numero, nome.strip(),
                sp_cnpj, sp_numero, sp_valor, observacao.strip())
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)


@router.post("/vinculos/desfazer")
def desfazer(cnpj: str = Form(...), numero: str = Form(...), competencia: str = Form(...),
             conciliacao_id: int = Form(...), db: Session = Depends(get_db)):
    serv.remover(db, competencia.strip(), cnpj, numero)
    return RedirectResponse(url=f"/resultado/{conciliacao_id}", status_code=303)
```

- [ ] **Step 6: Registrar router** — em `app/main.py`: `from app.routers import vinculos` (junto dos outros ~19) e `app.include_router(vinculos.router)` (junto dos outros ~74). Confirmar que "marcando divergência/vínculo" continua coberto pelo `guarda_origem` (POST cross-origin já é barrado globalmente).

- [ ] **Step 7: Rodar teste do serviço (passa)** — `pytest tests/test_vinculos.py -q`.

- [ ] **Step 8: Commit** — `git add -A && git commit -m "feat(v1): modelo/servico/rota de Vinculo (SP sem SIEG x nota em erro)"`.

---

### Task A2: Recálculo em `montar_resumo_e_itens` (consumir sp_sem_sieg + comparar valores)

**Files:**
- Modify: `app/routers/resultado.py` (`montar_resumo_e_itens` ~63-170; `_resumo_itens` ~173-178)
- Test: `tests/test_vinculos.py` (append)

**Interfaces:** `montar_resumo_e_itens(conc, tabelas=None, excecoes=None, validacoes=None, aceites=None, vinculos=None)`. Item da NOTA vinculada ganha `"vinculada": True, "vinculo_obs": <str>`; item `sp_sem_sieg` consumido ganha `"vinculado": True`. Resumo ganha `"qt_vinculadas"`.

**Algoritmo (pós-passo, após montar todos os `itens` e ANTES de contar buckets):**
1. `vinculos = vinculos or {}`.
2. Indexar os órfãos: `orfaos = {}` mapeando `(cnpj_norm, sp_numero_norm, round(sp_valor,2)) -> [item_dicts com veredito=="sp_sem_sieg"]` (usar `it["cnpj_norm"]`, `so_digitos(it_row.numero)`, `it["sp_bruto"]`/valor do SP). Guardar lista p/ desempate (primeiro não consumido).
3. Para cada `(cnpj_norm, numero_norm), v` em `vinculos.items()`: achar o item-NOTA principal com esse par; achar um órfão em `orfaos` cuja identidade casa `(v["sp_cnpj"], v["sp_numero"], round(v["sp_valor"],2))` ainda não consumido.
4. Se achou os dois: comparar valores NOTA×órfão com `valores_batem` (bruto: `it["sieg_bruto"]`×`orf["sp_bruto"]`; líquido: `it["sieg_liquido"]`×`orf["sp_liquido"]`; impostos: `it["sieg_imp"]`×`orf["sp_imp"]`), montar `status = "ok"` (tudo bate) ou `"diverg"` (com detalhe "bruto X≠Y; ..."). Setar no item-NOTA: `status_lancamento=status`, `detalhe_lancamento=detalhe`, `vinculada=True`, `vinculo_obs=v["obs"]`, e a identidade do alvo p/ o pacote (`vinculo_sp_cnpj=v["sp_cnpj"]`, `vinculo_sp_numero=v["sp_numero"]`, `vinculo_sp_valor=v["sp_valor"]` — consumidos pela Task A5); recomputar `erro_lanc_aberto = (status=="diverg") and not it["aceita"]` e daí `tem_erro`/`eh_gerenciada`. Marcar o órfão `vinculado=True`.
5. Contagens (mover/ajustar para DEPOIS do pós-passo): `qt_sp_sem_sieg` conta itens `veredito=="sp_sem_sieg" and not it.get("vinculado")`; novo `qt_vinculadas = sum(1 for it in prin if it.get("vinculada"))`; `qt_gerenciadas/qt_erros` já vêm de `prin` (refletem o pós-passo).

> Nota do desconto: usar os campos persistidos (`sieg_bruto/liquido/imp` × `sp_bruto/liquido/imp`) com `valores_batem` (tolerância R$0,05). No caso comum (nota sem desconto, mesmo valor) → tudo bate → Gerenciada.

- [ ] **Step 1: Testes (falham)** — append em `tests/test_vinculos.py` (usar `montar_resumo_e_itens` com um item NOTA `pendente`/faltou-lançar e um item `sp_sem_sieg` de mesmo CNPJ e valor):

```python
from app.routers.resultado import montar_resumo_e_itens
from app.services import aliquotas as serv_al

def _conc_nota_e_orfao(db, competencia="2026-07"):
    """Conciliação com: NOTA Sieg 300 'faltou lançar' + lançamento SP 'sem sieg'
    (mesmo CNPJ e valor, número 0)."""
    conc = Conciliacao(cnpj="11", competencia=competencia,
                       periodo_inicio="2026-07-01", periodo_fim="2026-07-31")
    db.add(conc); db.flush()
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="300",
        cnpj_fornecedor="54017315000170", nome_fornecedor="FORN", data_emissao="03/07/2026",
        valor_bruto=970.0, valor_liquido=970.0, imp_sieg=0.0,
        status_lancamento="falta", status_arquivo="ok", veredito="pendente", cancelada=False))
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="0",
        cnpj_fornecedor="54017315000170", nome_fornecedor="FORN", data_emissao="",
        valor_bruto=0.0, valor_liquido=0.0, sp_valor_bruto=970.0, sp_valor_liquido=970.0,
        imp_spdata=0.0, status_lancamento="", status_arquivo="", veredito="sp_sem_sieg",
        cancelada=False))
    db.commit(); db.refresh(conc); return conc


def test_vinculo_valores_batem_vira_gerenciada_e_tira_orfao(client):  # client garante schema
    db = SessionLocal(); serv_al.garantir_padrao(db)
    conc = _conc_nota_e_orfao(db)
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 970.0, "num errado")
    resumo, itens = montar_resumo_e_itens(conc, serv_al.listar(db), None, None, None,
                                          serv.mapa(db, "2026-07"))
    nota = next(i for i in itens if i["numero"] == "300")
    assert nota["vinculada"] and nota["eh_gerenciada"] and not nota["tem_erro"]
    assert resumo["qt_vinculadas"] == 1
    assert resumo["qt_sp_sem_sieg"] == 0            # o órfão foi consumido
    db.close()


def test_vinculo_valores_divergem_vira_ressalva(client):
    db = SessionLocal(); serv_al.garantir_padrao(db)
    conc = _conc_nota_e_orfao(db)
    # órfão com valor diferente da nota (970) -> divergência
    orf = db.query(ConciliacaoItem).filter(ConciliacaoItem.veredito == "sp_sem_sieg").first()
    orf.sp_valor_bruto = 900.0; orf.sp_valor_liquido = 900.0; db.commit()
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 900.0, "num errado, valor diverge")
    resumo, itens = montar_resumo_e_itens(conc, serv_al.listar(db), None, None, None,
                                          serv.mapa(db, "2026-07"))
    nota = next(i for i in itens if i["numero"] == "300")
    assert nota["vinculada"] and nota["tem_erro"]          # Ressalva (diverge)
    assert nota["status_lancamento"] == "diverg"
    db.close()
```

(Se `tests/test_vinculos.py` não tiver a fixture `client`, importar de `conftest`; o v1 usa fixture `client` de `tests/conftest.py`.)

- [ ] **Step 2: Rodar (falha)** — TypeError (param `vinculos` inexistente) / KeyError `qt_vinculadas`.

- [ ] **Step 3: Implementar** — em `app/routers/resultado.py`:
  - Assinatura: adicionar `vinculos=None` (default) em `montar_resumo_e_itens`.
  - No dict de cada item (~136), inicializar `"vinculada": False, "vinculo_obs": ""` e (nos sp_extra) `"vinculado": False`.
  - Após o loop que monta `itens` e ANTES de `prin = [...]` (~161): inserir o pós-passo descrito no Algoritmo (indexar órfãos, aplicar cada vínculo, comparar valores com `valores_batem` de `app.services.normalizacao`, atualizar item-NOTA e órfão).
  - Ajustar `qt_sp_sem_sieg` (linha 76) para contar do resultado final (itens não vinculados) — mover esse cálculo para depois do pós-passo, ou recomputar: `resumo["qt_sp_sem_sieg"] = sum(1 for it in itens if it["veredito"]=="sp_sem_sieg" and not it.get("vinculado"))`.
  - Adicionar `resumo["qt_vinculadas"] = sum(1 for it in prin if it.get("vinculada"))` junto das outras contagens (~167).
  - Em `_resumo_itens` (~175-178): passar `serv_vinculos.mapa(db, conc.competencia)` como 6º arg. Import `from app.services import vinculos as serv_vinculos`.

- [ ] **Step 4: Rodar (passa)** — `pytest tests/test_vinculos.py -q`.

- [ ] **Step 5: Regressão** — `pytest -q` (v1 inteiro, esperado 155 + novos).

- [ ] **Step 6: Commit** — `feat(v1): recalculo do Vinculo em montar_resumo_e_itens (consome orfao + compara valores)`.

---

### Task A3: Tela de Resultado (botão Vincular + seletor + selo + desfazer) + CSS

**Files:**
- Modify: `templates/resultado.html` (chip ~74; `<tr>` data ~119; selo ~139; bloco expand ~182-210; JS filtro ~296)
- Modify: `static/css/syncdata.css` (vars ~13; `.b-*` ~155; `.btn-mini` ~319)

- [ ] **Step 1: CSS teal** — em `static/css/syncdata.css`, ao lado de `--roxo` (linha 13): `--teal:#0E7C86; --teal-bg:#DCF0EE;   /* tratativa "Vinculada" */`. Adicionar `.b-teal{background:var(--teal-bg); color:var(--teal)}` (ao lado de `.b-roxo` ~155) e `.btn-mini.b-teal-btn{...}` (borda/hover teal, copiando `.b-roxo-btn` ~319-320).

- [ ] **Step 2: Chip do filtro** — em `resultado.html` (~74, junto de "Aceitas"): `<button class="chip chip-info" data-f="vinculada" onclick="setFiltro(this)">Vinculadas</button>`.

- [ ] **Step 3: `data-vinculada` na linha** — na `<tr>` (~119): `data-vinculada="{{ '1' if i.vinculada else '0' }}"`.

- [ ] **Step 4: Selo** — na célula de lançamento (~139, junto ao selo Aceita): `{%- if i.vinculada %} <span class="badge selo-sis b-teal" title="Vinculada manualmente ao lançamento do SpData: {{ i.vinculo_obs }}">Vinculada</span>{% endif -%}`.

- [ ] **Step 5: Botão Vincular + seletor + desfazer** — no bloco expand da linha (~182-210). Regras:
  - Mostrar o botão **"Vincular"** quando a nota está em erro por faltar lançar: `{% if i.status_lancamento == 'falta' and not i.vinculada %}`.
  - O seletor lista os itens `sp_sem_sieg` da MESMA nota-CNPJ, tirados de `itens` (Jinja): iterar `{% for o in itens if o.veredito == 'sp_sem_sieg' and not o.vinculado and o.cnpj_norm == i.cnpj_norm %}` como `<option>`/radios mostrando `nº {{ o.numero }} · {{ o.sp_bruto|num_br }} · {{ o.nome_fornecedor }}`. Um `<details>`/link **"ver todas"** repete o laço SEM o filtro de CNPJ.
  - Form: `<form method="post" action="/vinculos/marcar">` com hidden `cnpj`(=`i.cnpj_norm`), `numero`(=`i.numero_norm`), `nome`(=`i.nome_fornecedor`), `competencia`(=`resumo.competencia_raw`), `conciliacao_id`(=`c.id`); o `<select name="__alvo">`/radios entrega `sp_cnpj|sp_numero|sp_valor` — mais simples: cada opção com `value="{{o.cnpj_norm}}|{{o.numero}}|{{o.sp_bruto}}"` e um pequeno JS no submit que separa em hidden `sp_cnpj`/`sp_numero`/`sp_valor`; OU três `<option>`-triplas via radios com hiddens espelhados. Justificativa `<input name="observacao" required>`. Botão `<button class="btn-mini b-teal-btn">Vincular</button>`.
  - Quando `i.vinculada`: mostrar texto + `<form action="/vinculos/desfazer">` (hidden cnpj/numero/competencia/conciliacao_id) + `<button class="det-desfazer">desfazer vínculo</button>`.

- [ ] **Step 6: JS do filtro** — no switch (~296): `case 'vinculada': okS = principal && tr.dataset.vinculada === '1'; break;`.

- [ ] **Step 7: Verificação no navegador** — subir o app com `SYNCDATA_DB=dev_seed.db` (tem /resultado/1); confirmar botão "Vincular" numa nota "faltou lançar", seletor listando SP-sem-SIEG do mesmo CNPJ, e o selo teal após vincular. (Preview: `venv\Scripts\python -m uvicorn app.main:app --port 8799` com `SYNCDATA_ABRIR_NAVEGADOR=0`.)

- [ ] **Step 8: Commit** — `feat(v1): tela de Resultado com botao Vincular + seletor + selo teal`.

---

### Task A4: Excel — tratativa "Vinculada"

**Files:** Modify `app/services/exportacao.py`; Test `tests/test_exportacao.py` (append)

- [ ] **Step 1: Teste (falha)** — copiar `test_aceitas_no_resumo_situacao_e_guia` para `test_vinculadas_no_resumo_situacao_e_guia`: item com `{"vinculada": True, "vinculo_obs": "...", "eh_gerenciada": True, "tem_erro": False}`, `resumo["qt_vinculadas"]=1`; asserts: aba "Vinculadas", `res["Vinculadas (manual)"]==1`, "Vinculada" em Total, fornecedor na aba.

- [ ] **Step 2: Rodar (falha)**.

- [ ] **Step 3: Implementar** (espelho exato do Aceitas):
  - Cores: `_TEAL="FF0E7C86"`; `_FILL_TEAL=(PatternFill("solid", fgColor="FFDCF0EE"), Font(color=_TEAL, size=10))` (ao lado de `_ROXO`/`_FILL_ROXO`).
  - `_estilo_por_texto`: `if t == "Vinculada": return _FILL_TEAL`.
  - `_situacao_texto`: `if it.get("vinculada"): return "Vinculada"` (antes do fallback).
  - `_texto_recalc`: `if it.get("vinculada"): return ("VINCULADA: " + (it.get("vinculo_obs") or "") + ...).strip()`.
  - `_escrever_resumo`: linha `("Vinculadas (manual)", resumo.get("qt_vinculadas", 0))` (junto de "Aceitas (manual)").
  - `gerar_xlsx` categorias: `("Vinculadas", [i for i in prin if i.get("vinculada")])`.

- [ ] **Step 4: Rodar (passa)** + **Step 5: Commit** — `feat(v1): Vinculadas no relatorio .xlsx`.

---

### Task A5: `pacote_dados` — vínculo no dados.json

**Files:** Modify `app/services/pacote_dados.py`; Test `tests/test_vinculos.py` (append)

- [ ] **Step 1: Teste (falha)** — gerar pacote de uma conciliação com nota vinculada; asserts: `pacote["itens"][k]["vinculo"] == {"sp_cnpj":..., "sp_numero":"0", "sp_valor":970.0, "observacao":"..."}` e `pacote["resumo"]["vinculadas"] == 1`.

- [ ] **Step 2: Rodar (falha)**.

- [ ] **Step 3: Implementar** — em `_item` (~47, junto de `"aceita"`): `"vinculo": ({"sp_cnpj": it.get("...")...} if it.get("vinculada") else None)`. Precisa dos dados do vínculo no dict do item — expor no `montar_resumo_e_itens` os campos `vinculo_sp_cnpj/sp_numero/sp_valor` no item-NOTA (setados no pós-passo da Task A2). No resumo (~76): `"vinculadas": resumo.get("qt_vinculadas", 0)`.

- [ ] **Step 4: Rodar (passa)** + **Step 5: Commit** — `feat(v1): vinculo viaja no dados.json`.

---

# PARTE B — v2 (SyncDataServer) — espelho + multi-empresa

### Task B1: Modelo + serviço + router (empresa_id, conferir_empresa, log) + rótulos

**Files:** `app/models.py`, `app/services/vinculos.py` (create), `app/routers/vinculos.py` (create), `app/main.py`, `app/services/auditoria.py`, `tests/test_v2_vinculos.py`

- [ ] **Step 1: Teste do serviço escopado (falha)** — espelho de `test_v2_aceites.py::test_service_escopo_por_empresa`: `serv.salvar(db, empresa_id, "2026-07", cnpj, "300", nome, sp_cnpj, "0", 970.0, obs)`; `mapa(db, empresa_id, "2026-07")` traz `{sp_numero,sp_valor,obs}`; não vaza p/ outra empresa; `remover` ok.

- [ ] **Step 2: Rodar (falha)**.

- [ ] **Step 3: Modelo** — `Vinculo` com `empresa_id = Column(Integer, ForeignKey("empresa.id"), nullable=False, index=True)` e `__table_args__ = (UniqueConstraint("empresa_id","competencia","cnpj","numero", name="uq_vinculo_emp_comp_cnpj_num"),)`; demais colunas iguais à v1 (cnpj/numero/sp_cnpj/sp_numero/sp_valor/nome/observacao/criado_em).

- [ ] **Step 4: Serviço** — igual à v1, mas TODA função recebe `empresa_id` e filtra por ele (espelhar `app/services/aceites.py`).

- [ ] **Step 5: Router** — espelho de `app/routers/aceites.py`: form com `empresa_id: int` extra; `fora = conferir_empresa(db, conciliacao_id, empresa_id); if fora: return fora`; `serv.salvar(...)`; `_registrar(db, request, "lancamento_vinculado", empresa_id, nome or f"nota {numero}")`; desfazer → `"vinculo_desfeito"`. Copiar o helper `_registrar` de `aceites.py:13-20`.

- [ ] **Step 6: Rótulos** — em `app/services/auditoria.py` `ROTULOS`: `"lancamento_vinculado": "Lançamento vinculado"`, `"vinculo_desfeito": "Vínculo desfeito"`.

- [ ] **Step 7: Registrar router** — `app/main.py` import + `include_router` (junto de aceites).

- [ ] **Step 8: Rodar (passa)** + **Step 9: Commit**.

### Task B2: `montar_resumo_e_itens` v2 (mirror da Task A2, escopo por empresa)

**Files:** `app/routers/resultado.py`; Test `tests/test_v2_vinculos.py`

- Igual à Task A2, mas `_resumo_itens` chama `serv_vinculos.mapa(db, conc.empresa_id, conc.competencia)`. Testes espelham A2 (usar helpers de `tests/_fakes.py`/`conftest.py`; criar a conciliação com nota faltou-lançar + órfão sp_sem_sieg via `ConciliacaoItem` direto, como em `test_v2_aceites.py::_conc`). Rodar regressão (`pytest -q`, baseline 235). Commit.

### Task B3: Template + CSS v2 (mirror da Task A3)

Mesmos passos da A3 no `templates/resultado.html`/`static/css/syncdata.css` da v2. Os hiddens do form incluem `empresa_id`(=`c.empresa_id`). Verificação no navegador via app v2 (login + empresa ativa). Commit.

### Task B4: Excel v2 (mirror da Task A4)

Mesmos 6 pontos em `app/services/exportacao.py` da v2 + teste em `tests/test_exportacao.py`. Commit.

### Task B5: Import/export v2 (pacote_dados + importacao) + limpeza de teste

**Files:** `app/services/pacote_dados.py`, `app/services/importacao.py`, `tests/conftest.py`, `tests/test_v2_vinculos.py`

- [ ] **Step 1: Teste round-trip (falha)** — espelho de `test_import_reconstroi_aceite`: gerar pacote com nota vinculada → remover → `importacao.importar(...)` → confirmar `Vinculo` recriado por empresa/competência com sp_*/obs.

- [ ] **Step 2: pacote_dados v2** — `_item` ganha `"vinculo"` (igual à A5) e resumo `"vinculadas"`.

- [ ] **Step 3: importacao v2** — no loop de itens (~209, junto do aceite): `vinc = it.get("vinculo"); if vinc: serv_vinculos.salvar(db, empresa.id, competencia, cnpj_forn, numero, nome_forn, vinc.get("sp_cnpj"), vinc.get("sp_numero"), vinc.get("sp_valor"), vinc.get("observacao") or "")`. Import `from app.services import vinculos as serv_vinculos`.

- [ ] **Step 4: conftest** — em `tests/conftest.py::_limpar_tabelas`, importar e limpar o modelo `Vinculo` (junto de `AceiteDivergencia`).

- [ ] **Step 5: Rodar (passa)** + regressão (`pytest -q`, baseline 235 + novos) + **Commit**.

---

## Ordem & revisão

Executar A1→A5 (v1 completo e testado) e depois B1→B5 (v2). Cada tarefa: TDD (teste falha→passa) + revisão por tarefa. Ao fim, revisão de branch inteira. Trabalhar numa **branch** (`feat/vinculo-lancamento`), não na main. Deploy/merge fica com o usuário (v1 = rebuild do .exe; v2 = deploy_netuno.ps1).
