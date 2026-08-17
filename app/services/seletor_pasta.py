import logging
import subprocess

log = logging.getLogger(__name__)

_PS = r'''
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class _Fg {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
"@
# Janela-dona invisível, TopMost e em foreground: assim a caixa de seleção
# aparece SOBRE as demais janelas (antes ficava escondida atrás). O toque no
# ALT destrava o "foreground lock" do Windows p/ o SetForegroundWindow valer.
$dono = New-Object System.Windows.Forms.Form
$dono.TopMost = $true
$dono.ShowInTaskbar = $false
$dono.FormBorderStyle = 'None'
$dono.Size = New-Object System.Drawing.Size(1, 1)
$dono.StartPosition = 'Manual'
$dono.Location = New-Object System.Drawing.Point(-3000, -3000)
$dono.Show()
[_Fg]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)     # ALT down
[_Fg]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)     # ALT up
[_Fg]::SetForegroundWindow($dono.Handle) | Out-Null
$dono.Activate()
[System.Windows.Forms.Application]::DoEvents()

$dlg = New-Object System.Windows.Forms.FolderBrowserDialog
$dlg.Description = "Selecione a pasta com os PDFs das notas"
$res = $dlg.ShowDialog($dono)
$dono.Close()
if ($res -eq [System.Windows.Forms.DialogResult]::OK) {
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
            capture_output=True, encoding="utf-8", timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        # Erro real (PowerShell ausente, timeout, etc.) — distinto de um
        # cancelamento, que retorna stdout vazio e vira None em _parse_saida.
        log.warning("Falha ao abrir o seletor de pasta nativo", exc_info=True)
        return None
    return _parse_saida(r.stdout)
