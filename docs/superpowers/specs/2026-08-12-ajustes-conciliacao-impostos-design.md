# SyncData — Ajustes na Conciliação + Impostos (Fase A) — Design

- **Data:** 2026-08-12
- **Autor:** William Lopes (Audiecon) + Claude
- **Status:** Aguardando revisão do usuário
- **Fase:** A (ajustes de dados/exibição). A **Fase B** (absorver o Renew + preview de
  PDF + coluna de localização da NF) é um design próprio, **fora deste spec**.

---

## 1. Contexto e objetivo

A conciliação hoje mostra, por nota do Sieg, se foi **lançada** (SPData) e **arquivada**
(Renew), com um único valor (bruto). O cliente pediu enriquecer isso: comparar
**bruto/líquido e impostos** dos dois lados (Sieg × SPData), buscar/filtrar, padronizar o
número da NF, formatar moeda, e uma tela nova de **detalhamento de impostos** — tudo
saindo também no `.xlsx`.

Os impostos vêm de colunas que **já existem** nos arquivos, mas que os parsers atuais
**descartam**. Esta fase captura essas colunas e as expõe. Não há mudança no Renew (isso
é a Fase B); o Renew segue contribuindo só com o **valor** para o confronto de arquivo.

---

## 2. Escopo

### Dentro (Fase A)
- Capturar impostos de Sieg e SPData nos parsers.
- Guardar no `ConciliacaoItem` os valores/impostos dos **dois lados**.
- Confronto de valor que **abate descontos** do Sieg (sem divergência falsa).
- Tela de Resultado: busca/filtro, colunas agrupadas Sieg | SPData (bruto/líq/imp),
  número padronizado, moeda, chip `• desc`.
- Tela nova **"Detalhamento de Impostos"** (item de menu "Impostos").
- Export `.xlsx` com as colunas novas + aba "Impostos".

### Fora (Fase B, spec próprio)
- Absorver o Renew (OCR/poppler/tesseract) dentro do SyncData.
- Coluna com o **caminho do PDF** da NF + **preview** no sistema + abrir em 2ª tela.
- Fim da importação do `.xlsx` do Renew.

---

## 3. Modelo de impostos (validado com o cliente)

Correspondência Sieg × SPData (o SPData agrupa vários; o Sieg detalha):

| Imposto | Sieg | SPData |
|---|---|---|
| **ISS** | `ISS` | `ISSQN` |
| **INSS** | `INSS` | `INSS_PJ` + `INSS_AUTON` |
| **IRRF** | `IR` | `IRPJ` + `IR_AUTON` + `IR_COOP` |
| **CSRF** | `PIS` + `COFINS` + `CSLL` | `CSRF` |

- `ISS_Retido` (Sieg) é **informativo** (indica se houve retenção de ISS). Guardado como
  flag `iss_retido` (`Sim` → `True`); **não** é uma coluna a confrontar.
- **Total de retenções por lado** (a coluna "Imp" da tela principal):
  - **Sieg:** `INSS + IR + PIS + COFINS + CSLL + OutRetencoes + (ISS se iss_retido)`.
  - **SPData:** `ISSQN + INSS_PJ + INSS_AUTON + IRPJ + IR_AUTON + IR_COOP + CSRF`.
  - *(Ponto de calibração: incluir/ex­cluir `OutRetencoes` e a condição do ISS será
    reavaliado nos testes com dados reais.)*
- Só do Sieg (sem par no SPData), exibidos na tela de Detalhamento: `Deducoes`,
  `Desconto_Incondic`, `Desconto_Condic`, `OutRetencoes`, `Aliquota`, `Base_Calculo`.

---

## 4. Descontos (Opção 1 + 3)

- `descontos_sieg = Deducoes + Desconto_Incondic + Desconto_Condic`.
- **Confronto abate o desconto:** o valor de face que SPData/Renew registram já vem
  **líquido do desconto**, então o matcher compara
  `bruto_sieg_ajustado = Valor_Servico − descontos_sieg` contra `SPData.VALOR_BRUTO` e
  contra `Renew.valor`. Assim uma nota com desconto **não gera divergência falsa**.
  (O líquido já é comparado como antes — `Valor_Liquido` já abate tudo.)
- `tem_desconto = descontos_sieg > 0,05`. A nota ganha o chip **`• desc`** na tela.
- A quebra do desconto aparece na tela de **Detalhamento** e no `.xlsx` (não há coluna
  dedicada na tabela principal).
- **Exibição:** a tabela mostra os valores **reais** de cada lado (Sieg bruto = 10.000;
  SPData bruto = 9.385 numa nota com desconto de 615) — o chip `• desc` explica a
  diferença; o confronto, esse, usa o valor ajustado e não acusa divergência.

---

## 5. Mudanças no modelo de dados

### 5.1 Parsers
- **`parser_sieg` / `NotaSieg`** ganha: `iss`, `iss_retido` (bool), `inss`, `ir`, `pis`,
  `cofins`, `csll`, `deducoes`, `desc_incondic`, `desc_condic`, `outret`, `aliquota`,
  `base_calculo` — além de `valor_servico` (bruto) e `valor_liquido` já existentes.
  - Derivados: `descontos = deducoes + desc_incondic + desc_condic`;
    `csrf = pis + cofins + csll`;
    `bruto_ajustado = valor_servico − descontos`;
    `total_retencoes` (fórmula da seção 3).
- **`parser_spdata` / `LancamentoSpData`** ganha: `issqn`, `inss_pj`, `inss_auton`,
  `irpj`, `ir_auton`, `ir_coop`, `csrf` — além de `valor_bruto`/`valor_liquido`.
  - Derivados: `inss = inss_pj + inss_auton`; `ir = irpj + ir_auton + ir_coop`;
    `total_retencoes = issqn + inss + ir + csrf`.

### 5.2 Matcher
- `_avaliar` (frente de **lançamento**) passa a devolver **também a linha do SPData que
  casou** (o melhor candidato) — hoje devolve só o status. `conciliar` anexa os
  valores/impostos desse candidato ao item. (A frente de arquivo pode devolver a linha do
  Renew casada; na Fase A basta o valor — o caminho do PDF é Fase B.)
- `_cmp_spdata`/`_cmp_renew` comparam `nota.bruto_ajustado` (não o `valor_servico` cru).
- Sem candidato de lançamento → os campos SPData do item ficam vazios (nota "faltou
  lançar" não tem lado SPData).

### 5.3 `ConciliacaoItem` (novas colunas)
Além das atuais (`numero`, `nome_fornecedor`, `data_emissao`, `valor_bruto`(Sieg),
`valor_liquido`(Sieg), `status_*`, `detalhe_*`, `veredito`, `cancelada`):
- `sp_valor_bruto`, `sp_valor_liquido` (Float, nullable) — do lançamento casado.
- `imp_sieg`, `imp_spdata` (Float) — total de retenções de cada lado.
- `tem_desconto` (Boolean).
- `impostos_json` (String/JSON) — quebra completa por imposto dos dois lados +
  `deducoes/descontos/outret/aliquota/base_calculo` (Sieg), para a tela de Detalhamento
  e o export.

**Migração:** o app ainda não está em produção (sem dados reais do cliente), então o
schema é **recriado** — apagar `syncdata.db` na atualização. (Sem sistema de migração
por ALTER nesta fase; anotar como dívida se for para produção com histórico.)

---

## 6. Tela de Resultado (Conciliação)

- **Topo:** 🔎 **busca** (casa em nº / nome do fornecedor / valor) + **chips de filtro de
  status** (Todas · Gerenciadas · Ressalva · Pendentes). Filtragem **no navegador**
  (instantânea; ~130 linhas), escondendo as linhas que não batem.
- **Tabela agrupada** (cabeçalho de 2 níveis):

  `Nº NF | Fornecedor | Emissão | [Sieg: Bruto · Líq · Imp] | [SPData: Bruto · Líq · Imp]
  | Lançamento | Arquivo | Divergências`

  - Selos 🟢/🟡/🔴 em Lançamento e Arquivo.
  - Chip **`• desc`** ao lado do fornecedor quando `tem_desconto`.
  - Números em **moeda** pt-BR (`R$ 1.234,56`), alinhados (tabular).
  - **Nº padronizado** com zeros à esquerda (seção 9).
  - Rolagem horizontal própria da tabela (o corpo da página não rola lateralmente).

---

## 7. Tela "Detalhamento de Impostos"

- **Rota:** `GET /impostos` (conciliação **mais recente**) e
  `GET /impostos/{conciliacao_id}`. Item **"Impostos"** no menu lateral; link
  *"Ver impostos"* em cada tela de Resultado.
- **Tabela — uma linha por nota:**

  `Nº | Fornecedor | ISS(Sieg·SP·Δ) | INSS(Sieg·SP·Δ) | IRRF(Sieg·SP·Δ) |
  CSRF(Sieg·SP·Δ) | Descontos(Sieg) | Base Cálc.(Sieg) | Alíquota(Sieg) |
  Total ret.(Sieg·SP·Δ)`

  - `Δ` = diferença Sieg − SPData; linhas com `Δ ≠ 0` (fora da tolerância R$ 0,05)
    **destacadas**.
  - **Rodapé** com os totais gerais de cada coluna.
  - Filtro **"só divergências"** (chip) para focar no que não bate.
  - Reaproveita `impostos_json` do item (sem recalcular).

---

## 8. Export `.xlsx`

- Aba **"Conciliação"**: ganha as colunas de valores/impostos (Sieg e SPData) com
  **células numéricas em formato moeda** (`R$ #,##0.00`), somáveis no Excel. Nº
  padronizado. Bloco de totais no topo mantido.
- Nova aba **"Impostos"**: a mesma quebra da tela de Detalhamento (ISS/INSS/IRRF/CSRF
  Sieg·SP·Δ + Descontos/Base/Alíquota + totais).
- Mantém **"Faltou Lançar"** e **"Faltou Arquivar"** (ganham também Nº padronizado e
  moeda).
- Cores Moderatio como já é.

---

## 9. Padronização do número da NF

- Helper `padronizar_numeros(itens)`: calcula a **maior largura** (em dígitos) entre os
  números da conciliação e preenche todos com zeros à esquerda até essa largura
  (ex.: `18` → `000018` se o maior tiver 6 dígitos).
- Aplicado **só na exibição/export** — o **match continua usando o número normalizado**
  (sem zeros à esquerda), como já é.
- *Ressalva:* números "compostos" de 13 dígitos (Sieg/Renew) puxam a largura para cima;
  se ficar visualmente pesado, calibrar (ex.: teto de largura) nos testes.

---

## 10. Normalização e formatação (novos helpers)

- `moeda(v) -> "R$ 1.234,56"` (pt-BR: ponto de milhar, vírgula decimal) — para a tela.
- `padronizar_numeros(...)` (seção 9) — para tela e export.
- Reuso de `limpar_moeda` (parse) já existente; os novos helpers são de **formatação**.

---

## 11. Testes

- **Parsers:** Sieg e SPData capturam os impostos (valores não-zero de uma nota real com
  retenção, ex.: F&P — IR 308,70 / CSRF 956,97) e os derivados (`inss`, `ir`, `csrf`).
- **Matcher:** nota com desconto **não diverge** (abatimento); o item carrega os valores
  do lado SPData casado; nota "faltou lançar" fica sem lado SPData.
- **Formatação:** `moeda()` (mil/decimal), `padronizar_numeros()` (largura pelo maior).
- **Export:** aba "Impostos" existe e traz a quebra; célula de valor é numérica em
  formato moeda.
- **Rota Detalhamento:** `GET /impostos` (mais recente) e `/impostos/{id}` renderizam;
  `Δ` destacado; totais no rodapé.

---

## 12. Decisões travadas (resumo)

- Mapeamento de impostos da seção 3 (ISS↔ISSQN com ISS_Retido informativo; CSRF↔PIS+
  COFINS+CSLL; total = soma das retenções por lado).
- Descontos: abatem no confronto (sem divergência falsa) + chip `• desc` + detalhe na
  tela/planilha (sem coluna dedicada).
- Tabela agrupada Sieg | SPData; selos de status; moeda pt-BR; nº padronizado pela maior
  largura.
- Tela "Impostos" no menu (mais recente + por conciliação); inclui Base de Cálculo e
  Alíquota.
- Tudo replicado no `.xlsx` (aba "Conciliação" enriquecida + aba "Impostos").
- Banco recriado (sem migração pesada) — pré-produção.

## 13. Pontos de calibração (reavaliar nos testes com dados reais)
- Composição exata do "total de retenções" (OutRetencoes; ISS condicionado a retido).
- Largura máxima do número padronizado (por causa dos compostos de 13 dígitos).
- Se algum campo de imposto do SPData/Sieg precisa de tratamento especial (cooperativas,
  autônomos).
