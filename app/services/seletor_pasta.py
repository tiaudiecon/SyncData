import logging
import subprocess

log = logging.getLogger(__name__)

# INI-01: seletor de pasta que enxerga unidades de rede/UNC.
#
# O FolderBrowserDialog clássico (o que o Windows PowerShell 5.1 / .NET Framework
# entrega) usa a árvore antiga: sem barra de endereço p/ colar "\\marte\..." e com
# enumeração de "Rede" ruim. Trocamos pelo diálogo moderno do Windows
# (IFileOpenDialog + FOS_PICKFOLDERS): tem barra de endereço, mostra os drives
# mapeados e navega a rede. Toda a conversa COM (vtable puro IUnknown) roda dentro
# do C#, exposta num método estático — o PowerShell só chama e trata o foreground.
# Se o diálogo moderno falhar, cai no clássico (que ainda mostra "Rede"/drives).
_PS = r'''
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms

Add-Type @"
using System;
using System.Runtime.InteropServices;

[ComImport, Guid("42f85136-db7e-439c-85f1-e4075d135fc8"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IFileDialog {
  [PreserveSig] int Show(IntPtr parent);          // 1 (IModalWindow)
  void SetFileTypes(); void SetFileTypeIndex(); void GetFileTypeIndex(); void Advise(); void Unadvise();
  void SetOptions(uint fos); void GetOptions(out uint pfos); void SetDefaultFolder(); void SetFolder();
  void GetFolder(); void GetCurrentSelection(); void SetFileName(); void GetFileName();
  void SetTitle([MarshalAs(UnmanagedType.LPWStr)] string pszTitle); void SetOkButtonLabel(); void SetFileNameLabel();
  [PreserveSig] int GetResult(out IShellItem ppsi);
}
[ComImport, Guid("43826d1e-e718-42ee-bc55-a1e261c37bfe"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IShellItem {
  void BindToHandler(); void GetParent(); [PreserveSig] int GetDisplayName(uint sigdn, out IntPtr ppsz);
  void GetAttributes(); void Compare();
}
public static class SyncDataFolderPicker {
  public static string Pick(IntPtr owner, string titulo) {
    Type t = Type.GetTypeFromCLSID(new Guid("DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7")); // FileOpenDialog
    IFileDialog d = (IFileDialog)Activator.CreateInstance(t);
    d.SetOptions(0x60);                 // FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM
    d.SetTitle(titulo);
    if (d.Show(owner) != 0) return null;   // cancelado (ERROR_CANCELLED) ou erro
    IShellItem item; d.GetResult(out item);
    IntPtr p; item.GetDisplayName(0x80058000, out p);   // SIGDN_FILESYSPATH
    string caminho = Marshal.PtrToStringUni(p);
    Marshal.FreeCoTaskMem(p);
    return caminho;
  }
}
"@

# Janela-dona invisível, TopMost e em foreground: garante que a caixa apareça
# SOBRE as demais janelas. O toque no ALT destrava o "foreground lock".
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class _Fg {
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
}
"@
$dono = New-Object System.Windows.Forms.Form
$dono.TopMost = $true; $dono.ShowInTaskbar = $false
$dono.FormBorderStyle = 'None'
$dono.Size = New-Object System.Drawing.Size(1, 1)
$dono.StartPosition = 'Manual'
$dono.Location = New-Object System.Drawing.Point(-3000, -3000)
$dono.Show()
[_Fg]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero)     # ALT down
[_Fg]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)     # ALT up
$dono.Activate()
[System.Windows.Forms.Application]::DoEvents()

$titulo = "Selecione a pasta com os PDFs das notas"
$caminho = $null
try {
    $caminho = [SyncDataFolderPicker]::Pick($dono.Handle, $titulo)
} catch {
    # Fallback: diálogo clássico (ainda mostra "Rede" e drives mapeados).
    $fb = New-Object System.Windows.Forms.FolderBrowserDialog
    $fb.Description = $titulo
    $fb.ShowNewFolderButton = $false
    if ($fb.ShowDialog($dono) -eq [System.Windows.Forms.DialogResult]::OK) {
        $caminho = $fb.SelectedPath
    }
}
$dono.Close()
if ($caminho) { Write-Output $caminho }
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
