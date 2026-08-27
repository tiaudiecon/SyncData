# Tratativa "Aceita" — aceitar divergência de valor/arquivo

**Data:** 2026-08-27
**Aplica-se a:** SyncData (v1, cliente `.exe`) **e** SyncDataServer (v2, servidor).

## Problema

Hoje há duas tratativas manuais, ambas para a **divergência de impostos**:
- **Validação** (`ValidacaoImposto`): nota sem erro de imposto, por nota+competência.
- **Exceção** (`ExcecaoFornecedor`): fornecedor dispensado, permanente por CNPJ.

Falta tratar a **divergência de valor (Sieg×SPData) ou de arquivo** — o veredito
`ressalva` (está nos dois lados mas um valor/arquivo diverge) ou `pendente` (faltou
lançar/arquivar). Hoje esses contam como **Erro** e **travam a exportação** (o botão
"Exportar dados" só habilita com Erros=0). Existem situações (poucas) em que essa
divergência é **legítima/correta** e o operador precisa liberar aquela nota.

## Solução: tratativa "Aceita"

Nova tratativa manual, **espelho do mecanismo da Validação**, mas para o erro de
valor/arquivo:

- **Nome/rótulo:** "Aceita" · **ação:** "Aceitar divergência".
- **Cor da tag:** **roxo/violeta** (novo token `--roxo`), distinta das duas azuis
  (Validada/Exceção) e sem conflito com verde(ok)/âmbar(diverg)/vermelho(erro).
- **Escopo:** por **nota + competência** (chave competência+CNPJ+número), como a Validação.
- **Justificativa obrigatória** (campo de texto), gravada no registro.
- **Efeito:** a nota deixa de ser Erro e passa a **Gerenciada** → destrava a exportação.
- **Abrangência:** limpa o erro de veredito `ressalva` **e** `pendente` (valor que diverge
  OU arquivo/lançamento que falta/diverge, mas está correto).
- **Ortogonal** às outras: NÃO mexe na divergência de imposto (`pendencia_sieg`), que
  continua sendo resolvida por Validar/Exceção. Uma nota com os dois tipos usa as duas.

## Modelo de dados

Nova tabela `AceiteDivergencia`, análoga a `ValidacaoImposto`:
- **v1:** `id, competencia, cnpj, numero, nome, observacao, criado_em`; unique
  `(competencia, cnpj, numero)`.
- **v2:** + `empresa_id` (FK), unique `(empresa_id, competencia, cnpj, numero)`.
- Criada automaticamente pelo `create_all` (tabela nova; sem micro-migração de coluna).

## Serviço

`app/services/aceites.py` espelhando `validacoes.py`:
`salvar(...)`, `remover(...)`, `mapa(db[, empresa_id], competencia) -> {(cnpj_norm, numero_norm): obs}`.

## Recálculo (resultado.py `montar_resumo_e_itens`)

Carregar o mapa de aceites da competência. Para cada item principal:
- `is_aceita = aceites.get((cnpj_norm, numero_norm)) is not None`.
- `erro_lanc_aberto = (veredito in ("ressalva","pendente")) and not is_aceita`.
- `tem_erro = principal and (erro_lanc_aberto or pend_aberta)`.
- `eh_gerenciada = principal and not tem_erro`.
  (Equivalente ao atual quando não há aceite; uma ressalva/pendente aceita vira Gerenciada.
  Se ainda houver `pend_aberta` de imposto, continua Erro — ortogonalidade preservada.)
- Novos campos no item: `aceita` (bool), `aceita_obs` (str). Novo total `qt_aceitas`.

## UI (resultado.html)

- **Tag roxa "Aceita"** na coluna Lançam. quando `i.aceita` (junto de Validada/Exceção).
- **Chip de filtro "Aceitas"** ao lado de "Validadas" (informativo). `data-aceita` na linha;
  case `aceita` no `filtrar()`.
- **No detalhe da nota**, quando o erro for `ressalva`/`pendente`:
  - se ainda não aceita: formulário **"Aceitar divergência"** (justificativa obrigatória) →
    `POST /aceites/marcar`;
  - se já aceita: mostra a justificativa + **desfazer** (`POST /aceites/desfazer`).
  - Colocado no bloco de Divergências (Lançamento/Arquivo) do detalhe.

## Rotas

`app/routers/aceites.py` (ou junto de validações), espelhando validações:
- `POST /aceites/marcar` — campos cnpj, numero, nome, observacao, competencia,
  conciliacao_id (**v2:** + empresa_id do hidden do form).
- `POST /aceites/desfazer` — cnpj, numero, competencia, conciliacao_id (**v2:** + empresa_id).

## Exportação / import

- **v1 e v2** `pacote_dados._item`: adicionar `"aceita": {"observacao": ...}` quando aceita
  (como `validada`), e `qt_aceitas` no resumo. Bump não necessário (aditivo; VERSAO fica 2).
- **v2** `importacao.py`: reconstruir o `AceiteDivergencia` da empresa a partir do item
  `aceita` (como já faz com `validada`/`excecao`).

## Gestão (v2)

- Ações de auditoria `divergencia_aceita` / `divergencia_desfeita` em `ROTULOS`; `auditoria.registrar`
  nas rotas marcar/desfazer (best-effort, só se salvou), com usuário + empresa ativa.

## Testes

- Serviço aceites (salvar/remover/mapa, unicidade).
- Recálculo: uma ressalva aceita → `tem_erro=False`, `eh_gerenciada=True`, `qt_aceitas=1`,
  `qt_erros` cai; desfazer volta a Erro. Ortogonalidade: ressalva aceita + imposto aberto
  continua Erro.
- Rota marcar/desfazer (v2: escopo por empresa; 200/redirect).
- Export: item aceito carrega `aceita`; (v2) import reconstrói.
- (v2) `/gestao` registra o evento.

## Fora de escopo

- Aceite permanente por CNPJ (é por nota+competência, por decisão).
- Alterar o significado de Validação/Exceção.
