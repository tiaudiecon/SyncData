# SyncData — Documento de Design (Especificação)

- **Data:** 2026-08-10
- **Autor:** William Lopes (Audiecon) + Claude
- **Status:** Aguardando revisão do usuário
- **Produto:** SyncData — aplicativo desktop portátil de conciliação de notas fiscais de serviço

---

## 1. Contexto e objetivo

O cliente precisa **confrontar três bases de informação** para provar que todas as
notas fiscais de serviço (NFS-e) que recebeu foram **gerenciadas** — ou seja,
**lançadas** no seu sistema **e arquivadas** (PDF baixado/renomeado). O SyncData
cruza os três arquivos e entrega um relatório claro do que está OK e do que ficou
pendente.

As três bases:

| Base | O que é | Origem |
|---|---|---|
| **SpData** | Lançamentos que o **cliente** digitou no programa SpData (o "razão" dele) | `.txt` |
| **Sieg** | Todas as **NFS-e** relacionadas ao CNPJ do cliente | `.xlsx` (relatório NFS-e ABRASF) |
| **Renew** | Todas as notas **baixadas e renomeadas** (arquivadas) | `.xlsx` |

### Características de distribuição

- **Portátil (`.exe` standalone)** — roda na máquina local do cliente, **sem
  servidor central** (diferente do Integra GRP e do Folha Flow, que são web).
- **Banco leve:** SQLite embarcado.
- **Multi-cliente genérico, 1 CNPJ por cópia:** o app não tem CNPJ fixo no código;
  o cliente digita **uma vez** o seu CNPJ (na primeira execução), o app lembra e
  nunca mais pergunta.
- **UX "burra de simples":** digitar CNPJ (1x) → subir 3 arquivos → clicar
  **Conciliar** → ver resultado / exportar.

---

## 2. Escopo

### Dentro do escopo (v1)

- Conciliação de **notas de serviço (NFS-e)** apenas.
- **Modelo A:** o **Sieg é a lista-mestra** (o que *deveria existir*). Para cada nota
  do Sieg, verifica-se se foi **lançada** (SpData) e **arquivada** (Renew).
- Histórico das conciliações no SQLite.
- Exportação `.xlsx` nas cores do sistema.

### Fora do escopo (futuro)

- **Notas de produto (NF-e).** Exigem uma lista-mestra própria (relatório NF-e do
  Sieg). A arquitetura deve deixar espaço para isso sem retrabalho.
- **Modelo B** (cruzamento "todos contra todos", divergências em qualquer direção).
  A arquitetura do motor deve ser desenhada para evoluir para B depois.
- Versão web/centralizada, multiusuário, login.

---

## 3. Entradas — layout real dos três arquivos

### 3.1 SpData (`.txt`)

- **Formato:** separado por `|` (pipe), codificação **Latin-1 / Windows-1252**.
- **Primeira linha é cabeçalho.**
- **Colunas:**
  `EMISSAO | ENTRADA | NOTA | CNPJ_CPF | FORNECEDOR | ORIGEM | VALOR_BRUTO |
  VALOR_LIQUIDO | IR_COOP | IRPJ | IR_AUTON | CSRF | INSS_PJ | INSS_AUTON | ISSQN |
  GRUPO | DESC_GRUPO | SUBGRUPO | DESC_SUBGRUPO | ITEM | DESC_ITEM`
- **Campos usados:** `NOTA` (nº), `CNPJ_CPF` (14 dígitos, sem máscara — pode ser CPF
  de 11 para autônomo), `FORNECEDOR` (nome), `EMISSAO` (data `AAAA-MM-DD`),
  `VALOR_BRUTO`, `VALOR_LIQUIDO` (decimal com ponto).
- **Observação:** `NOTA` pode ser `0` (lançamentos sem nota, ex.: banco). Esses
  registros simplesmente nunca serão "encontrados" por uma nota do Sieg — não
  precisam de tratamento especial, mas não devem quebrar o parser.

### 3.2 Sieg — NFS-e ABRASF (`.xlsx`)

- **1 planilha, cabeçalho na linha 1, 35 colunas.**
- **Colunas:**
  `Numero | Dt_Emissao | Dt_Competencia | Prestador | RzPrestador | Uf_Prest |
  Mun_Prest | Insc_Prest | Tomador | RzTomador | Uf_Toma | Cod_Mun_Toma |
  Optante_SN | Cod_Servico | CNAE | Valor_Servico | IR | ISS | ISS_Retido | CSLL |
  Deducoes | PIS | COFINS | INSS | Desconto_Incondic | Desconto_Condic |
  OutRetencoes | Aliquota | Base_Calculo | Valor_Liquido | Dt_Cancelamento |
  Motivo_Cancel | Numero_Nota_Cancel | Status | Pdf`
- **Direção:** interessa a nota em que o **cliente é o `Tomador`**. Linhas em que o
  cliente é `Prestador` (notas que ele emitiu) são **ignoradas**.
- **O `Prestador` é o fornecedor** — é o CNPJ que casa com o SpData (`CNPJ_CPF`) e o
  Renew (`CNPJ do Emissor`).
- **Campos usados:** `Numero`, `Dt_Emissao` (datetime), `Prestador` (CNPJ sem
  máscara), `RzPrestador` (nome), `Valor_Servico` (**bruto**), `Valor_Liquido`
  (**líquido**), `Status`, `Dt_Cancelamento`.
- **Status:** autorizada = `"Autorizado o uso da NFS-e"`; canceladas têm
  `Dt_Cancelamento`/`Motivo_Cancel` preenchidos e/ou `Status` diferente.

### 3.3 Renew (`.xlsx`)

- **1 planilha, cabeçalho na linha 1, 9 colunas.**
- **Colunas:**
  `Status | Tipo de Nota | Nome Original | Novo Nome | Fornecedor Emitente |
  CNPJ do Emissor | Nº NF / Série | Data de Emissão | Valor da NF`
- **Campos usados:** `Nº NF / Série` (ex.: `"202069 / 7"` ou `"1924136"` — número +
  série opcional), `CNPJ do Emissor` (**com máscara**, ex.: `39.362.611/0001-15`),
  `Fornecedor Emitente` (nome), `Data de Emissão` (datetime), `Valor da NF`
  (= **líquido**, conforme informado pelo cliente).
- **Observação:** o Renew traz produto **e** serviço (`Tipo de Nota`). No Modelo A só
  as linhas que casarem com uma nota do Sieg (serviço) são relevantes; as demais
  ficam de fora naturalmente.

---

## 4. Normalização das chaves

Antes de qualquer comparação, normalizar:

- **CNPJ/CPF** → apenas dígitos (remove `.`, `/`, `-`, espaços). Compara como está
  (11 ou 14 dígitos).
- **Número da NF** → remover a "/série" (parte após `/`), remover espaços e **zeros à
  esquerda** para efeito de comparação (guardar o valor original para exibição).
  Ex.: `"000972 / 1"` → `972`; `"4291"` → `4291`.
- **Valor** → converter para número; comparação com **tolerância de R$ 0,05**.
- **Data** → comparar por **dia** (ignora hora).

---

## 5. Regra de conciliação (o coração do sistema)

### 5.1 Filtro e universo

1. Ler o Sieg e manter apenas as linhas onde **`Tomador` == CNPJ do cliente**.
2. Separar **autorizadas** × **canceladas**.
3. **Universo da conciliação** = notas **autorizadas** com `Tomador` = cliente.
   As **canceladas** vão para um grupo **informativo** (não são exigidas em lançamento
   nem arquivo).

### 5.2 Índices

- Índice do **SpData**: `(numero_norm, cnpj_norm)` → lista de lançamentos.
- Índice do **Renew**: `(numero_norm, cnpj_norm)` → lista de registros.
- A chave do Sieg para busca é `(numero_norm(Numero), cnpj_norm(Prestador))`.

### 5.3 Match em cascata (por frente)

Para **cada nota do Sieg** (universo), avalia-se **duas frentes independentes**:

- **Lançamento** → busca no índice do **SpData**.
- **Arquivo** → busca no índice do **Renew**.

Cada frente recebe um status pela cascata (do mais rígido ao mais frouxo):

- 🟢 **Conciliada (alta confiança)** — existe candidato em que batem
  **Nº + CNPJ + Emissão + Valor** (dentro da tolerância).
- 🟡 **Conciliada com divergência** — existe candidato por **Nº + CNPJ**, mas
  Emissão e/ou Valor divergem. Registra-se **qual campo divergiu** (data / bruto /
  líquido) e os dois valores comparados. (Escolhe-se o candidato de melhor score.)
- 🔴 **Não encontrada** — não há candidato por **Nº + CNPJ**. É a pendência real:
  "faltou lançar" ou "faltou arquivar".

**Quais valores cada frente compara:**

- **SpData (lançamento):** `EMISSAO` × `Dt_Emissao`; `VALOR_BRUTO` × `Valor_Servico`;
  `VALOR_LIQUIDO` × `Valor_Liquido`.
- **Renew (arquivo):** `Data de Emissão` × `Dt_Emissao`; `Valor da NF` ×
  `Valor_Liquido` (só líquido — o Renew não traz bruto).

**Múltiplos candidatos** (raro): escolher o de melhor score (data + valores batendo).

### 5.4 Veredito da nota

Combinando as duas frentes:

- ✅ **Gerenciada** — lançada **e** arquivada, ambas 🟢.
- ⚠️ **Gerenciada com ressalva** — está nas duas frentes, mas alguma é 🟡
  (divergência de valor/data).
- ❌ **Pendente** — alguma frente é 🔴 (faltou lançar e/ou faltou arquivar).

---

## 6. Saídas

### 6.1 Tela de resultado

1. **Cartões de resumo:** total de notas do Sieg (universo) e R$ total; quantas
   ✅ gerenciadas, quantas ⚠️ com ressalva, quantas **faltou lançar**, quantas
   **faltou arquivar**, quantas **canceladas** (informativo).
2. **Tabela filtrável** — uma linha por nota: Nº, Data, Fornecedor, Valor, status de
   **Lançamento** (🟢/🟡/🔴), status de **Arquivo** (🟢/🟡/🔴), detalhe da
   divergência. Filtro por status (ex.: "mostrar só pendentes"). Cores do Moderatio.
3. Botão **Exportar .xlsx**.

### 6.2 Export `.xlsx` (3 abas, cores do sistema)

1. **"Conciliação"** — todas as notas do Sieg com os 2 status, com um **bloco de
   totais no topo** (a prova completa).
2. **"Faltou Lançar"** — apenas as 🔴 de lançamento.
3. **"Faltou Arquivar"** — apenas as 🔴 de arquivo.

> *Interpretação de "3 abas" a confirmar no review: mantém a "Conciliação" completa
> (com resumo no topo) em vez de uma aba "Resumo" separada.*

---

## 7. Telas e fluxo

1. **Setup (1ª execução)** — pede **CNPJ** (+ razão social opcional). Salva no SQLite
   e marca "já configurado". Não pergunta de novo.
2. **Conciliar (home)** — mostra o CNPJ ativo (com link discreto para editar) + **3
   slots de upload** (SpData `.txt` · Sieg `.xlsx` · Renew `.xlsx`) + botão grande
   **Conciliar**.
3. **Resultado** — conforme seção 6.1.
4. **Histórico** — lista das conciliações passadas (data/hora, arquivos, totais);
   permite **reabrir** o resultado e **reexportar** o `.xlsx`.
5. **Configurações** — editar o CNPJ do cliente.

---

## 8. Modelo de dados (SQLite)

- **`config`** — `cnpj_cliente`, `razao_social` (opcional), `configurado` (flag).
  Uma linha só (chave/valor ou registro único).
- **`conciliacao`** (uma por execução) — `id`, `data_hora`, `cnpj`,
  `arquivo_spdata_nome`, `arquivo_sieg_nome`, `arquivo_renew_nome`,
  `total_universo`, `valor_total`, `qt_gerenciadas`, `qt_ressalva`,
  `qt_falta_lancar`, `qt_falta_arquivar`, `qt_canceladas`.
- **`conciliacao_item`** (uma por nota do Sieg) — `id`, `conciliacao_id`, `numero`,
  `cnpj_fornecedor`, `nome_fornecedor`, `data_emissao`, `valor_bruto`,
  `valor_liquido`, `status_lancamento`, `status_arquivo`, `detalhe_divergencia`,
  `cancelada`.

O histórico é reconstruído a partir de `conciliacao` + `conciliacao_item` (não é
necessário guardar os arquivos originais).

---

## 9. Arquitetura técnica

Clonar o **modo desktop do Integra GRP**:

- **FastAPI + uvicorn** (servidor local), **Jinja2** (templates), **SQLAlchemy +
  SQLite**, empacotado com **PyInstaller**.
- Reaproveitar o **design Moderatio** (tokens de cor navy/bordô/creme, fontes
  Fraunces + Inter) e o padrão dos exports `.xlsx` do Integra.
- Ao iniciar o `.exe`: sobe o uvicorn em `localhost` e abre o navegador.

**Alternativas descartadas:** GUI Tkinter/PySimpleGUI (exe menor, mas jogaria fora o
Moderatio e o reuso do Integra); Electron (peso desnecessário).

### Estrutura de pastas proposta

```
SyncData/
  app/
    main.py                # cria o FastAPI, registra routers, sobe o servidor
    database.py            # engine SQLite + sessão SQLAlchemy
    models/                # config, conciliacao, conciliacao_item
    routers/
      setup.py             # 1ª execução (CNPJ)
      conciliar.py         # upload dos 3 arquivos + disparo
      resultado.py         # tela de resultado
      historico.py         # lista + reabrir/reexportar
      configuracoes.py     # editar CNPJ
    services/
      normalizacao.py      # CNPJ, número, valor, data
      parser_spdata.py
      parser_sieg.py
      parser_renew.py
      matcher.py           # cascata + veredito (preparado p/ Modelo B)
      exportacao.py        # .xlsx 3 abas, cores Moderatio
    templates/             # base.html + telas (Moderatio)
    static/                # css/js/favicon
  tests/
  docs/
  run.py
  SyncData.spec            # PyInstaller
  build_release.ps1
  requirements.txt
```

---

## 10. Testes (pytest)

- **Parsers:** SpData (pipe/Latin-1, `NOTA=0`), Sieg (filtro Tomador, autorizada ×
  cancelada), Renew (máscara CNPJ, "nº/série", valor líquido).
- **Normalização:** CNPJ/CPF, número (zeros à esquerda, série), valor (tolerância),
  data (por dia).
- **Matcher:** casos 🟢/🟡/🔴 em cada frente; divergência só de data; só de valor;
  tolerância de R$ 0,05 no limite; nota cancelada; múltiplos candidatos; veredito
  ✅/⚠️/❌.
- **Export:** gera as 3 abas com os totais corretos.

---

## 11. Empacotamento (`.exe`)

- `SyncData.spec` clonado do `IntegraGRP.spec` (incluir `templates/`, `static/`,
  ícone, dados).
- `build_release.ps1` adaptado.
- SQLite criado no primeiro uso, ao lado do executável (ou em pasta de dados do
  usuário) — definir no plano de implementação.

---

## 12. Decisões travadas (resumo)

- Modelo A (Sieg mestre); arquitetura preparada para B.
- Sieg: cliente = Tomador; Prestador = fornecedor.
- Match em cascata 🟢/🟡/🔴 (chave forte Nº+CNPJ+Emissão+Valor → relaxa p/ Nº+CNPJ).
- Valores: bruto (SpData↔Sieg) e líquido (SpData↔Sieg↔Renew). Tolerância R$ 0,05.
- Duas frentes (lançar + arquivar) → veredito ✅/⚠️/❌.
- Canceladas: informativo.
- Portátil (`.exe`), SQLite, 1 CNPJ por cópia (digitado 1x), multi-cliente genérico.
- Histórico persistido. Export `.xlsx` em 3 abas. Nome: **SyncData**.

## 13. Pontos em aberto para o review

1. Confirmar a composição das **3 abas** do export (seção 6.2): manter "Conciliação"
   completa com resumo no topo, ou trocar por uma aba "Resumo" dedicada?
2. Onde o **arquivo SQLite** deve ficar (ao lado do `.exe` × pasta de dados do
   usuário no Windows)? — decidir no plano de implementação.
3. Futuro: relatório **NF-e (produtos)** do Sieg como segunda lista-mestra; **Modelo
   B**.
