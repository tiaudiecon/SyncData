# SyncData — Absorver o Renew + Preview de PDF (Fase B) — Design

- **Data:** 2026-08-13
- **Autor:** William Lopes (Audiecon) + Claude
- **Status:** Aguardando revisão do usuário
- **Fase:** B. Depende da Fase A (impostos), já na `main`.

---

## 1. Contexto e objetivo

Hoje o SyncData confronta 3 arquivos, sendo o **Renew `.xlsx`** um upload manual: o usuário
precisa rodar o **Renew** (programa à parte, OCR de PDFs) antes, gerar a planilha e enviá-la.
São **dois programas** e um passo manual no meio.

A Fase B faz o SyncData **absorver o Renew**: passa a existir **um único executável**. O
usuário aponta a **pasta dos PDFs** das NFS-e; o SyncData roda o Renew por baixo (renomeia +
extrai), lê o resultado e concilia — e ainda passa a mostrar **onde está o PDF** de cada nota
arquivada, com **preview embutido** e opção de **abrir numa segunda tela**.

O Renew continua contribuindo **só com a frente de "arquivo"** (a prova de que a nota foi
arquivada) e agora com o **caminho do PDF**. Ele **não** entra em impostos — isso já vem de
Sieg/SPData (Fase A).

---

## 2. Escopo

### Dentro (Fase B)
- Embutir o Renew (exe + `poppler/` + `tesseract/` + `clientes.txt`) no distribuível do
  SyncData.
- Trocar o **upload do Renew `.xlsx`** por **apontar uma pasta de PDFs** (botão nativo do
  Windows), com execução **automática** do Renew nessa pasta.
- **Barra de progresso ao vivo** ("Processando notas… X/Y") enquanto o Renew roda (OCR pode
  levar minutos na 1ª vez).
- Ler a saída do Renew (`Relatório Renew.xlsx` gerado na pasta) com o parser **já existente**;
  capturar também o nome do PDF renomeado (coluna "Novo Nome").
- Tela de Resultado: **coluna "PDF"** nas notas arquivadas, com **preview** (painel lateral com
  `<iframe>`) e botão **"Abrir"** (aba/janela nova → segunda tela).
- Persistir o caminho da pasta e o nome do PDF por nota, para o preview funcionar depois
  (Histórico).

### Fora (Fase B)
- Mudar a lógica do match ou os impostos (Fase A, estável).
- Alterar o Renew internamente (usamos o `.exe` como está, via CLI).
- Baixar PDFs da prefeitura/portal (o Renew processa uma pasta **local**; o download continua
  manual, fora do app).

---

## 3. Fluxo do usuário (tela de Conciliar)

Hoje: **3 uploads** (SPData `.txt`, Sieg `.xlsx`, Renew `.xlsx`).

Passa a ser:
- SPData `.txt` — upload (igual).
- Sieg `.xlsx` — upload (igual).
- **Pasta dos PDFs** — botão **"Procurar…"** abre a janela nativa do Windows; o caminho
  escolhido preenche um campo (editável, e **lembra o último** usado). O upload do Renew
  **some**.

Ao clicar **Conciliar**:
1. O front envia os 2 arquivos + o caminho da pasta para `POST /processar`.
2. O servidor salva os 2 arquivos num diretório de trabalho, cria um **job** e devolve na hora
   um `job_id` (o Renew roda numa thread em segundo plano). A tela vai para o estado
   **"Processando notas… X/Y"**.
3. O front consulta `GET /processar/{job_id}` a cada ~1s e atualiza a barra.
4. Ao terminar, o status vira `pronto` com o `conciliacao_id`; o front redireciona para
   `/resultado/{id}`.

---

## 4. Rodar o Renew (subprocess + progresso)

### 4.1 Chamada
- O Renew embutido é chamado como **CLI**: `Renew_10.4.exe "C:\pasta"` (sem argumento ele
  abriria a GUI — por isso sempre passamos a pasta).
- É executado com o **cwd na própria pasta do Renew** (onde estão `poppler/`, `tesseract/`,
  `clientes.txt`), para ele achar as dependências.
- Localização do exe embutido: em `run.py` já resolvemos `sys._MEIPASS` quando congelado
  (onedir → `_internal/`). O Renew fica em `<_MEIPASS>/renew/Renew_10.4.exe`; em dev, num
  caminho configurável (env `SYNCDATA_RENEW_DIR`, com fallback para a pasta de distribuição do
  Renew).

### 4.2 Job em segundo plano
- Novo serviço `renew_runner.py` + um **registro de jobs em memória** (`dict` `job_id → estado`).
  Estado: `fase` ("ocr" | "conciliando" | "pronto" | "erro"), `atual`, `total`, `conciliacao_id`,
  `erro`.
- O job: (a) roda o Renew na pasta, acompanhando o progresso; (b) lê a saída; (c) roda o matcher
  com os arquivos já lidos; (d) salva a `Conciliacao` (com o caminho da pasta); (e) marca
  `pronto` + `conciliacao_id`.
- A thread não usa a `Session` do request (que fecha); abre a sua própria sessão do banco.

### 4.3 De onde vem o "X/Y"
- **Total** = nº de arquivos `.pdf` na pasta.
- **Atual** = progresso do Renew. Dois sinais possíveis, definidos **na implementação rodando o
  Renew real** (mesmo método de calibração que usamos para "Renew = bruto"):
  - **Primário:** ler o que o Renew imprime (stdout/`LOG_GERAL_OCR.txt`) e extrair "X/Y" ou
    contar linhas de "arquivo processado".
  - **Fallback garantido (independe do formato de saída):** a cada ~1s, contar quantos PDFs na
    pasta já foram **renomeados** para o padrão do Renew (`E_*.pdf`) vs. o total.
- Se o formato do stdout do Renew não for confiável, fica só o fallback — que sempre funciona.

---

## 5. Saída do Renew → frente "arquivo" + caminho do PDF

- O Renew gera na pasta o **`Relatório Renew.xlsx`** (nome fixo) e renomeia os PDFs.
- O SyncData **lê esse xlsx da pasta** com o parser **já existente** (`ler_renew`) — a frente de
  "arquivo" é idêntica à de hoje; só muda a **origem** (planilha nasce na pasta em vez de vir por
  upload). `ler_renew` já aceita um caminho/arquivo; passamos o caminho do xlsx.
- **Novo:** capturar a coluna **"Novo Nome"** (o PDF renomeado) em `RegistroRenew.arquivo_pdf`.
  Caminho completo do PDF = `pasta \ Novo Nome`.

### 5.1 `RegistroRenew` (parser_renew.py)
Ganha o campo:
```python
arquivo_pdf: str = ""   # "Novo Nome" = nome do PDF renomeado pelo Renew
```
Preenchido a partir da coluna "Novo Nome" (via `indice(mapa, "Novo Nome")`; opcional — se
faltar, fica `""`).

### 5.2 Matcher (matcher.py)
Hoje a frente de arquivo **descarta** o candidato casado:
```python
arq, _ = _avaliar(nota, idx_rn.get(nota.cnpj_prestador, []), _cmp_renew)
```
Passa a **guardar** o candidato do Renew, para levar o `arquivo_pdf`:
- `ItemConciliacao` ganha `arquivo_row: object = None`.
- `conciliar`: `arq, arq_row = _avaliar(...)`; `ItemConciliacao(nota, lanc, arq, veredito,
  lanc_row, arq_row)`.
- Sem candidato de arquivo (🔴 faltou arquivar) → `arquivo_row = None` → sem PDF.

### 5.3 Persistência (persistencia.py + models.py)
- `Conciliacao` ganha `pasta_pdfs = Column(String, nullable=True)` — o caminho da pasta daquela
  execução.
- `ConciliacaoItem` ganha `arquivo_pdf = Column(String, nullable=True)` — o nome do PDF casado.
- `salvar_conciliacao` passa a receber a pasta (via `nomes["pasta_pdfs"]`) e a gravar
  `arquivo_pdf=(item.arquivo_row.arquivo_pdf if item.arquivo_row else None)`.

---

## 6. Preview do PDF + abrir em segunda tela

### 6.1 Servir o PDF (rota interna) — `routers/pdf.py`
- `GET /pdf/{item_id}` → busca o `ConciliacaoItem`; monta o caminho
  `Conciliacao.pasta_pdfs / item.arquivo_pdf`; **valida** que o caminho resolvido está **dentro**
  de `pasta_pdfs` (trava contra path traversal) e que o arquivo existe; devolve
  `FileResponse(..., media_type="application/pdf")` com `Content-Disposition: inline`.
- Se a pasta foi movida/apagada ou o arquivo sumiu → **404** com mensagem amigável
  ("PDF não encontrado — a pasta pode ter sido movida.").

### 6.2 Tela de Resultado (resultado.html)
- **Coluna "PDF"** nas linhas com frente de arquivo 🟢/🟡 **e** `arquivo_pdf` presente:
  - **Preview:** botão que abre um **painel lateral** com o PDF embutido
    (`<iframe src="/pdf/{item}">`). Clicar em outra nota troca o preview; um "×" fecha o painel.
  - **Abrir:** botão/link `href="/pdf/{item}" target="_blank"` → abre em **aba/janela nova**
    (que o usuário arrasta para o segundo monitor).
- Linhas sem PDF (faltou arquivar) mostram um "—" discreto na coluna.

---

## 7. Seletor de pasta nativo — `services/seletor_pasta.py`

- O SyncData roda **no navegador**, que **não entrega o caminho de uma pasta** ao servidor. Como
  o app é **local** (servidor = máquina do usuário), abrimos um diálogo nativo **no servidor**.
- `GET /procurar-pasta` → o servidor executa um **PowerShell** com
  `System.Windows.Forms.FolderBrowserDialog` (rodado com `-STA`, em subprocess próprio — não
  mistura com o thread do uvicorn) e captura o caminho escolhido no stdout. Devolve
  `{"pasta": "<caminho>"}` (ou `{"pasta": null}` se cancelado).
- O JS preenche o campo com o caminho e o guarda como "último usado".
- **Detalhe:** o diálogo precisa vir para frente; usar um form dono com `TopMost` para não
  aparecer atrás do navegador.
- **Só Windows** — que é o alvo do produto (é um `.exe` Windows).

---

## 8. Empacotamento (SyncData.spec)

- Adicionar a **distribuição do Renew inteira** como `datas` do SyncData, sob `renew/`
  (exe + `poppler/` + `tesseract/` + `clientes.txt` + `Logo.ico`), copiada verbatim da pasta de
  distribuição do Renew.
- **Tamanho:** o distribuível cresce **~130 MB** (o Renew é um onefile de ~132 MB). É grande,
  mas é um programa de mesa, e elimina instalar/abrir dois programas.
- **MAX_PATH piora** (o Renew fica em subpasta funda, `_internal/renew/tesseract/...`). Regra
  reforçada: **instalar raso** (ex.: `C:\SyncData\`) — documentar no README/instalador.
- Observação: o Renew onefile se **extrai no `%TEMP%`** a cada execução (comportamento do
  PyInstaller onefile) → alguns segundos de partida por rodada; aceitável. (Se virar incômodo,
  uma build onedir do Renew removeria isso — fora do escopo agora.)

---

## 9. Erros e casos de borda

- **Pasta vazia / sem PDFs / caminho inexistente** → validar **antes** de rodar; erro amigável na
  tela de Conciliar (não cria job).
- **Renew falha / trava / retorna código ≠ 0** → job `erro`; mostrar as últimas linhas do log do
  Renew + "não consegui processar a pasta"; **não** gera conciliação pela metade.
- **`Relatório Renew.xlsx` aberto no Excel** (trava a escrita) → o Renew não consegue gravar →
  job `erro` com "feche a planilha 'Relatório Renew.xlsx' e tente de novo".
- **Notas marcadas "revisar" pelo Renew** → aviso na tela ("o Renew marcou N notas para
  revisão"); as que não deram para ler caem naturalmente como 🔴 "faltou arquivar".
- **Pasta movida/apagada antes do preview** (via Histórico) → `/pdf/{item}` responde 404 com a
  mensagem amigável (seção 6.1).

---

## 10. Mudanças no modelo de dados (resumo)

| Onde | Campo novo | Tipo | Para quê |
|---|---|---|---|
| `RegistroRenew` | `arquivo_pdf` | `str = ""` | nome do PDF ("Novo Nome") |
| `ItemConciliacao` | `arquivo_row` | `object = None` | candidato do Renew casado |
| `Conciliacao` | `pasta_pdfs` | `String` (nullable) | caminho da pasta dos PDFs |
| `ConciliacaoItem` | `arquivo_pdf` | `String` (nullable) | PDF casado da nota |

**Migração:** colunas novas **nullable** (registros antigos ficam sem — sem quebrar). Como o app
ainda é pré-produção (sem histórico do cliente), recriar `syncdata.db` na atualização é aceitável;
se preferir preservar, um `ALTER TABLE ADD COLUMN` de guarda no start resolve. Decisão travada:
**recriar o banco** (igual à Fase A), anotando a dívida do ALTER caso vá a produção com histórico.

---

## 11. Arquivos novos / alterados

### Novos
- `app/services/renew_runner.py` — localiza o Renew embutido, roda na pasta, acompanha progresso,
  devolve o caminho do `Relatório Renew.xlsx`; + **registro de jobs** em memória.
- `app/services/seletor_pasta.py` — abre a janela nativa (PowerShell `FolderBrowserDialog`) e
  devolve o caminho.
- `app/routers/processar.py` — `POST /processar` (inicia o job), `GET /processar/{job_id}`
  (status/progresso), `GET /procurar-pasta` (abre o diálogo).
- `app/routers/pdf.py` — `GET /pdf/{item_id}` (serve o PDF inline, com trava de caminho).

### Alterados
- `app/services/parser_renew.py` — capturar "Novo Nome" → `RegistroRenew.arquivo_pdf`.
- `app/services/matcher.py` — `ItemConciliacao.arquivo_row`; `conciliar` guarda o candidato do
  Renew.
- `app/services/persistencia.py` — gravar `pasta_pdfs` e `arquivo_pdf`.
- `app/models.py` — `Conciliacao.pasta_pdfs`, `ConciliacaoItem.arquivo_pdf`.
- `app/routers/conciliar.py` — a rota `POST /conciliar` síncrona com 3 uploads dá lugar ao fluxo
  de job (o `POST /processar` + progresso); a tela inicial passa a ter o picker de pasta.
- `templates/conciliar.html` — campo de pasta + botão "Procurar…" + tela/estado de progresso
  (barra "X/Y" com polling).
- `templates/resultado.html` — coluna "PDF" + painel de preview + botão "Abrir".
- `SyncData.spec` — bundle da distribuição do Renew sob `renew/`.

---

## 12. Testes

- **`renew_runner`** — testado com um **Renew falso** (script Python pequeno que imprime
  progresso e escreve um `Relatório Renew.xlsx` de mentira), **sem** depender do Renew real de
  130 MB nem de OCR. Verifica: o job avança o progresso, produz o caminho do xlsx e transita
  `ocr → conciliando → pronto`; caminho de **erro** quando o "Renew" retorna código ≠ 0.
- **`parser_renew`** — lê "Novo Nome" para `arquivo_pdf`; ausência da coluna → `""`.
- **`matcher`** — o `arquivo_pdf` do candidato do Renew casado chega ao `ItemConciliacao`
  (`arquivo_row`); 🔴 faltou arquivar → `arquivo_row = None`.
- **`persistencia`** — `pasta_pdfs` e `arquivo_pdf` gravados; item sem arquivo casado grava
  `arquivo_pdf = None`.
- **Rota `/pdf`** — serve um PDF temporário (inline) e **bloqueia** caminho fora da pasta
  (path traversal → sem vazamento); arquivo inexistente → 404.
- **Job/status** — `GET /processar/{job_id}` reflete as transições com um runner **stub**.
- **`seletor_pasta`** — a janela nativa não é testável automaticamente; isolar a chamada do
  PowerShell numa função fina e testar só o **parse** do caminho retornado (o diálogo em si é
  teste manual).

---

## 13. Pontos de calibração (rodando o Renew real na implementação)

- **Sinal de progresso** exato (parse do stdout/log do Renew vs. contagem de `E_*.pdf` na pasta).
- Formato/nome real das colunas do `Relatório Renew.xlsx` gerado pela **V10.4** (confirmar
  "Novo Nome" e o status de "revisar").
- Comportamento de **re-rodar** numa pasta já processada (o cache do Renew deve tornar rápido; a
  barra deve ir a 100% quase na hora).
- Tempo de partida do Renew onefile (extração no `%TEMP%`) e efeito na experiência.

---

## 14. Decisões travadas (resumo)

- **Approach A:** embutir o `Renew_10.4.exe` e orquestrar via **subprocess** (CLI
  `Renew_10.4.exe "pasta"`). Um único executável.
- Entrada da pasta por **botão nativo do Windows** ("Procurar…"), com execução **automática** do
  Renew ao conciliar.
- **Barra de progresso ao vivo** ("X/Y"), via job em segundo plano.
- Frente de "arquivo" continua vindo do `Relatório Renew.xlsx` (parser atual); **novo**: caminho
  do PDF via "Novo Nome".
- Preview em **painel lateral** (`<iframe>`) + **"Abrir"** em aba nova (segunda tela).
- Persistir `pasta_pdfs` + `arquivo_pdf` para o preview funcionar pelo Histórico.
- Banco **recriado** (colunas novas nullable) — pré-produção.
