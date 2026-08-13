import subprocess

_PS = r'''
Add-Type -AssemblyName System.Windows.Forms
$dlg = New-Object System.Windows.Forms.FolderBrowserDialog
$dlg.Description = "Selecione a pasta com os PDFs das notas"
$dono = New-Object System.Windows.Forms.Form
$dono.TopMost = $true
if ($dlg.ShowDialog($dono) -eq [System.Windows.Forms.DialogResult]::OK) {
    Write-Output $dlg.SelectedPath
}
'''


def _parse_saida(stdout) -> "str | None":
    """Última linha não-vazia do stdout = o caminho escolhido."""
    linhas = [l.strip() for l in (stdout or "").splitlines() if l.strip()]
    return linhas[-1] if linhas else None


def escolher_pasta() -> "str | None":
    """Abre o seletor de pasta nativo do Windows (o servidor roda na máquina do
    usuário). Devolve o caminho escolhido, ou None se cancelado/erro."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-STA", "-Command", _PS],
            capture_output=True, text=True, timeout=300,
        )
    except Exception:
        return None
    return _parse_saida(r.stdout)
