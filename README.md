# SyncData

Confronta 3 arquivos (SpData `.txt`, Sieg NFS-e `.xlsx`, Renew `.xlsx`) e mostra,
para cada nota de serviço do Sieg em que o cliente é Tomador, se ela foi
**lançada** (SpData) e **arquivada** (Renew).

## Rodar em desenvolvimento
```
python -m venv venv
venv\Scripts\pip install -r requirements-dev.txt
venv\Scripts\python run.py
```
Abre em http://127.0.0.1:8000. Na 1ª vez, informe o CNPJ do cliente.

## Testes
```
venv\Scripts\python -m pytest
```

## Gerar o .exe
```
powershell -ExecutionPolicy Bypass -File build_release.ps1
```
O executável fica em `dist\SyncData\SyncData.exe` (pasta portátil).
