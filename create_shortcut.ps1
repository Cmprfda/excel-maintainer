$ErrorActionPreference = 'Stop'

try {
    $repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

    $pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $pythonExe) {
        try { $pythonExe = (& py -3 -c "import sys; print(sys.executable)") } catch { $pythonExe = $null }
    }

    $pythonwExe = $null
    if ($pythonExe) {
        $candidate = Join-Path (Split-Path $pythonExe) 'pythonw.exe'
        if (Test-Path $candidate) { $pythonwExe = $candidate }
    }

    $lnkPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Excel Maintainer.lnk'
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($lnkPath)

    if ($pythonwExe) {
        $Shortcut.TargetPath = $pythonwExe
        $Shortcut.Arguments = '"' + (Join-Path $repoRoot 'app.py') + '"'
        $Shortcut.IconLocation = $pythonwExe + ',0'
    } else {
        # No windowless interpreter found: fall back to run.bat (shows a console window).
        $Shortcut.TargetPath = Join-Path $repoRoot 'run.bat'
        $Shortcut.WindowStyle = 7
    }

    $Shortcut.WorkingDirectory = $repoRoot
    $Shortcut.Save()

    Write-Output "Atalho criado em: $lnkPath"
}
catch {
    Write-Error $_
    exit 1
}
