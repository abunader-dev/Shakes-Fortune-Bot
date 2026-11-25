$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
$python  = Get-Command python  -ErrorAction SilentlyContinue

if (-not $pythonw -and -not $python) {
    Write-Host "[ERROR] Python no encontrado." -ForegroundColor Red
    Write-Host "Instala Python desde https://www.python.org/ y marca 'Add Python to PATH'."
    Read-Host "Presiona ENTER para salir"
    exit 1
}

if ($pythonw) {
    Start-Process -FilePath $pythonw.Source -ArgumentList "gui.py" -WorkingDirectory $PSScriptRoot
} else {
    & $python.Source "gui.py"
}
