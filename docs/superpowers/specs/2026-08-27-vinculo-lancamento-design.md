# Vínculo manual de lançamento (SP sem SIEG ↔ nota em erro) — Design

**Data:** 2026-08-27
**Vale para as DUAS versões:** SyncData (v1, cliente/.exe) e SyncDataServer (v2, servidor).

## Problema

Quando o número da nota vem errado (ou `0`) no SpData, o match automático não
encontra o lançamento da nota do Sieg. Resultado atual:

- A nota do **Sieg** aparece como **"faltou lançar"** (erro).
- O **mesmo lançamento** está lá na lista **"SP Data sem SIEG"** (mesmo CNPJ e valor,
  só o número da nota diverge).

São dois órfãos que são a **mesma nota**, mas o sistema não consegue casá-los porque a
única chave que ele tem (o número) está errada de um lado. Perdemos o match.

Princípio que originou o pedido (ver memória `preservar-dado-mesmo-incompleto`): não
descartar/perder o dado por um detalhe; e, quando o detalhe quebra o match automático,
oferecer um caminho **manual** em vez de esconder. O usuário rejeitou explicitamente
afrouxar o match automático (casar por CNPJ+valor sem número) por ser arriscado —
prefere o **vínculo com o operador analisando**.

## Objetivo

Um botão **"Vincular"** na tela de Resultado, no mesmo estilo de Validar/Exceção/
Aceitar, que permite ao operador reconectar uma nota em erro ("faltou lançar") com um
lançamento da lista "SP sem SIEG". O sistema passa a tratar aquele lançamento como o
lançamento da nota, **confere os valores/impostos** e atualiza o veredito.

## Decisões (confirmadas com o usuário)

1. **Efeito do vínculo = vincular + conferir valores.** Depois do vínculo, o lançamento
   escolhido vale como o lançamento da nota e roda a **mesma conferência do match
   automático** (`_cmp_spdata`: bruto, líquido e retenções). Se bate → **Gerenciada**;
   se diverge → **Ressalva** (e aí o operador pode usar o **Aceita** por cima, que já
   existe). Nada é escondido.

2. **Candidatos = mesmo CNPJ, com opção de ampliar.** O seletor começa mostrando só os
   lançamentos "SP sem SIEG" do **mesmo CNPJ** da nota (com número, valor e fornecedor
   à mostra); um link **"ver todas"** amplia para todos os "SP sem SIEG" (caso raro do
   CNPJ divergente).

3. **Selo/tag = "Vinculada", cor teal (#0E7C86).** Distinta das demais (Gerenciada=verde,
   Validada/Exceção=azul, Aceita=roxo, Ressalva=amarelo).

4. **Escopo = por nota + competência** (vale só naquele mês), igual a Aceite/Validação.
   Reversível ("Desfazer vínculo").

5. **Fronteira: só o lado do lançamento (SpData).** Se a nota também estiver "faltou
   arquivar" (Renew com número errado), esse lado segue pendente — não existe hoje um
   "Renew sem SIEG" para vincular; trata-se à parte (Aceita, ou vínculo de arquivo no
   futuro). Fora de escopo agora.

## Fluxo na tela de Resultado

1. Nas notas em erro por **"faltou lançar"** (lançamento = FALTA), aparece o botão
   **"Vincular"** ao lado dos botões existentes.
2. Ao clicar, abre um seletor (mesmo padrão visual do formulário de Aceita/Validada) com
   os lançamentos "SP sem SIEG" do **mesmo CNPJ**: linha por lançamento mostrando
   **número, valor bruto/líquido e fornecedor**; link "ver todas" para ampliar.
3. O operador seleciona um lançamento, escreve uma **justificativa obrigatória** e
   confirma.
4. A nota passa a exibir o selo **"Vinculada"** (teal) e o veredito recalculado
   (Gerenciada/Ressalva); o lançamento vinculado **some da lista "SP sem SIEG"**.
5. **"Desfazer vínculo"** (nas notas vinculadas) reverte: a nota volta a "faltou lançar"
   e o lançamento volta para "SP sem SIEG".

## Modelo de dados

Nova tabela **`VinculoLancamento`** (criada por `create_all`, sem migração):

- v1 (SyncData / SQLite): `competencia`, `sieg_numero`, `sp_cnpj`, `sp_numero`,
  `sp_valor` (bruto, p/ desempate), `observacao`, timestamps.
- v2 (SyncDataServer / Postgres): idem + `empresa_id` (escopo por empresa, como
  ExcecaoFornecedor/ValidacaoImposto/AceiteDivergencia). Constraint única composta
  `(empresa_id, competencia, sieg_numero)` — uma nota só tem um vínculo por competência.

**Chave lógica do vínculo:** `(empresa, competência, número da nota Sieg)` →
identidade do lançamento SpData `(cnpj + número + valor)`. Guardar a identidade do
lançamento (e não o id da linha) faz o vínculo **sobreviver a refazer a conciliação**:
se o mesmo lançamento reaparecer, o vínculo re-aplica (igual a Aceite/Validação).

**Desempate:** se houver mais de um lançamento "SP sem SIEG" com a mesma identidade
(mesmo cnpj+número+valor — raro), o recálculo casa o **primeiro ainda não consumido**.
O operador vê valor/fornecedor ao escolher, então o vínculo aponta o lançamento certo;
lançamentos idênticos são intercambiáveis para efeito de conferência.

## Recálculo (display-time, sem re-rodar `conciliar`)

Aplicado em `montar_resumo_e_itens` (o mesmo lugar onde Aceite/Validação/Exceção já são
aplicados), a partir de um **mapa de vínculos** `(cnpj_norm, sieg_numero_norm) → vínculo`:

Para cada nota principal do Sieg em erro por "faltou lançar":
- Se existe vínculo, procurar o item "SP sem SIEG" da conciliação que casa com a
  identidade guardada (`cnpj + número + valor`).
- Achou → tratar como o lançamento da nota:
  - Rodar a conferência de valores (bruto/líquido/impostos) entre a nota (Sieg) e o
    lançamento (SpData) — reaproveitando a lógica de `_cmp_spdata` sobre os valores
    persistidos.
  - `status_lancamento` da nota vira `ok` (bate) ou `diverg` (com o detalhe da
    divergência); veredito recalculado por `_veredito` → **gerenciada** ou **ressalva**.
  - Marcar a nota com `vinculada=True` + `vinculo_obs` (para o selo e o "Desfazer").
  - **Consumir** o item "SP sem SIEG" correspondente: remover do subconjunto "SP sem
    SIEG" e da contagem `qt_sp_sem_sieg` (não é mais órfão).
- Interage com as demais tratativas de forma ortogonal: se após o vínculo a nota ficar
  Ressalva, o operador ainda pode **Aceitar** a divergência (Aceite continua por nota+
  competência). Vínculo cuida da IDENTIDADE (qual lançamento é), Aceite cuida de ACEITAR
  a divergência de valor.

`eh_gerenciada`/`tem_erro` seguem a mesma regra já existente (nota vinculada sem erro em
aberto conta como Gerenciada).

## Rotas / serviço (espelhar o padrão de `aceites`)

- Serviço `vinculos.py`: `mapa(...)`, `salvar(...)`, `remover(...)`, `candidatos(...)`
  (lista os "SP sem SIEG" do CNPJ / todos), tudo escopado por empresa no v2.
- v1: `POST /vincular` e `POST /vincular/desfazer` (single-user).
- v2: idem, com `conferir_empresa` (form vs conciliação, igual às outras tratativas) e
  log no painel de Gestão (`auditoria.registrar`: `lancamento_vinculado` /
  `vinculo_desfeito`).

## Relatório .xlsx

Tratamento **"Vinculada"** igual às demais (padrão do Aceitas): situação "Vinculada" na
aba Total, contagem **"Vinculadas (manual)"** no Resumo, guia própria **"Vinculadas"**,
cor teal na célula de situação.

## Import/export (pacote `dados.json`, v1 → v2)

O `pacote_dados` (v1) passa a carregar os vínculos da conciliação; o `importacao` (v2)
reconstrói os `VinculoLancamento` da empresa/competência (isolado por empresa, como
Aceite/Validação/Exceção já fazem). Formato aditivo/retrocompatível.

## Fora de escopo (agora)

- Vínculo do lado do **arquivo (Renew)**: não há "Renew sem SIEG"; a nota que também
  estiver "faltou arquivar" segue pendente nesse lado (usar Aceita).
- Afrouxar o match automático (casar por CNPJ+valor sem número) — rejeitado pelo usuário.

## Testes (as duas versões)

- Vínculo com valores que batem → nota vira Gerenciada e o lançamento sai de "SP sem
  SIEG".
- Vínculo com valores que divergem → nota vira Ressalva com o detalhe; depois Aceita
  por cima → Gerenciada.
- Desfazer → nota volta a "faltou lançar" e o lançamento volta para "SP sem SIEG".
- Candidatos: só mesmo CNPJ por padrão; "ver todas" amplia.
- Sobrevive a refazer a conciliação (mesma identidade re-aplica).
- v2: escopo por empresa (não vincula/enxerga lançamento de outra empresa); log no
  Gestão.
- Excel: guia "Vinculadas" + "Vinculadas (manual)" no Resumo.
- Import/export: o vínculo viaja no `dados.json` e é reconstruído no v2.
