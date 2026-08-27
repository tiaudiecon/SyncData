# Plano — Tratativa "Aceita" (aceitar divergência de valor/arquivo)

> Executar por superpowers:subagent-driven-development ou inline (o autor tem o padrão da Validação em mãos). Espelha `validacoes.py`.

**Goal:** Nova tratativa "Aceita" (roxa, por nota+competência, com justificativa) que limpa o erro de ressalva/pendente (valor/arquivo) → nota vira Gerenciada e destrava a exportação. Nas duas versões.

**Global Constraints:** espelhar `ValidacaoImposto`/`validacoes.py`/rota de validações; tabela nova criada por `create_all`; recálculo em `resultado.montar_resumo_e_itens`; ortogonal à divergência de imposto. Ver spec `2026-08-27-aceite-divergencia-design.md`.

---

## Task 1 — v1 (SyncData, cliente)

**Files:**
- `app/models.py` — nova `AceiteDivergencia(id, competencia, cnpj, numero, nome, observacao, criado_em)`, unique `(competencia, cnpj, numero)`.
- `app/services/aceites.py` — `salvar(db, competencia, cnpj, numero, nome, observacao)`, `remover(db, competencia, cnpj, numero)`, `mapa(db, competencia) -> {(cnpj_norm, numero_norm): obs}`. (Copiar `validacoes.py`, tirar imposto.)
- `app/routers/aceites.py` — `POST /aceites/marcar`, `POST /aceites/desfazer` (espelha validações; volta p/ `/resultado/{conciliacao_id}`). Registrar no `app/main.py`.
- `app/routers/resultado.py` — carregar `mapa` de aceites da competência e passar p/ `montar_resumo_e_itens`; computar `is_aceita`, `erro_lanc_aberto`, novo `tem_erro`, `eh_gerenciada = principal and not tem_erro`; itens ganham `aceita`/`aceita_obs`/`cnpj_norm`/`numero_norm`; resumo ganha `qt_aceitas`.
- `app/services/pacote_dados.py` — `_item`: `"aceita": ({"observacao": it.get("aceita_obs")} if it.get("aceita") else None)`; resumo `"aceitas": resumo.get("qt_aceitas", 0)`.
- `templates/resultado.html` — tag roxa "Aceita" na coluna Lançam.; `data-aceita` na linha; chip "Aceitas" ao lado de "Validadas" + case `aceita` no `filtrar()`; no detalhe (bloco Divergências), quando `veredito in (ressalva,pendente)`: form "Aceitar divergência" (justificativa) ou, se já aceita, obs + "desfazer".
- `static/css/syncdata.css` — token `--roxo` + `.badge.b-roxo` + chip da tag.
- `tests/` — `test_aceites.py` (serviço + recálculo + rota + export).

**Passos (TDD):**
- [ ] Testes falhando: serviço `salvar/remover/mapa`; recálculo (ressalva aceita → tem_erro=False, eh_gerenciada=True, qt_aceitas=1; desfazer reverte; ressalva aceita + imposto aberto continua Erro); rota marcar/desfazer devolve 303 p/ resultado; export inclui `aceita`.
- [ ] Rodar e ver falhar.
- [ ] Modelo + serviço + rota + registro no main.
- [ ] Recálculo no resultado.py (com o cuidado da ortogonalidade).
- [ ] pacote_dados + template + CSS.
- [ ] Rodar suíte inteira (baseline v1 = 132 testes) verde.
- [ ] Commit `feat: tratativa "Aceita" (aceitar divergencia de valor/arquivo)`.

---

## Task 2 — v2 (SyncDataServer, servidor)

Espelha a Task 1 **+ multi-empresa + import + Gestão**:

**Files (além dos equivalentes da Task 1):**
- `app/models.py` — `AceiteDivergencia` com `empresa_id` (FK) + unique `(empresa_id, competencia, cnpj, numero)`.
- `app/services/aceites.py` / `app/routers/aceites.py` — escopo por `empresa_id` (empresa ativa; no marcar/desfazer o `empresa_id` vem do hidden do form, como validações v2).
- `app/services/importacao.py` — reconstruir `AceiteDivergencia` da empresa a partir do item `aceita` (como faz com `validada`/`excecao`).
- `app/services/auditoria.py` — `ROTULOS`: `divergencia_aceita`/`divergencia_desfeita`; `registrar` nas rotas marcar/desfazer (best-effort, só se salvou), usuário + empresa ativa.
- `app/services/pacote_dados.py` (v2 tem sua cópia) — mesmo campo `aceita`.
- `templates/resultado.html`, `static/css/syncdata.css` — iguais à v1.
- `tests/` — `test_v2_aceites.py` (serviço/recálculo/rota escopada), + import reconstrói o aceite, + `/gestao` registra o evento; `conftest._limpar_tabelas` inclui `AceiteDivergencia`.

**Passos (TDD):** análogos à Task 1 + escopo empresa + import + log. Baseline v2 = 203 testes. Commit `feat: tratativa "Aceita" no servidor (multi-empresa + import + log Gestao)`.

---

## Distribuição (pós-implementação, do usuário)

- **v1:** rebuild do `.exe` (C:/sb2) + hot-patch/zip + reenviar (fluxo de sempre).
- **v2:** `deploy_netuno.ps1` (a tabela nova nasce sozinha no `create_all`).
