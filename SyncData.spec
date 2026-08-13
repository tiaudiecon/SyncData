# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os

_RENEW_DIR = os.environ.get("SYNCDATA_RENEW_DIR", os.path.join('..', 'Renew'))
datas = [('templates', 'templates'), ('static', 'static'), (_RENEW_DIR, 'renew')]
binaries = []
hiddenimports = ['uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
    'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan', 'uvicorn.lifespan.on']

# pydantic_core traz uma extensão compilada (Rust) que o PyInstaller não acha
# sozinho — sem coletar, o .exe compila mas quebra ao rodar com
# "No module named 'pydantic_core._pydantic_core'". collect_all pega o binário.
for _pkg in ('pydantic', 'pydantic_core'):
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

# collect_submodules varre só .py, então a extensão compilada (o .pyd) é copiada
# como binário mas NÃO registrada como módulo. Sem isto, o .exe quebra ao rodar
# com "No module named 'pydantic_core._pydantic_core'". Registra explicitamente.
hiddenimports += ['pydantic_core._pydantic_core']

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='SyncData',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=True, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=['Logo.ico'])
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[],
    name='SyncData')
