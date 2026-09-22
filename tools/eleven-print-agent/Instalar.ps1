$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
if ($env:OS -ne 'Windows_NT') { throw 'Instale somente no Windows da loja.' }
$root = Join-Path $env:LOCALAPPDATA 'ElevenPrint'
New-Item -ItemType Directory -Force -Path $root | Out-Null

$printers = @([System.Drawing.Printing.PrinterSettings]::InstalledPrinters)
$desired = 'HP Laserjet M14-M17'
if ($printers -notcontains $desired) {
    Write-Host 'Impressoras instaladas:'
    for ($i = 0; $i -lt $printers.Count; $i++) { Write-Host "$($i + 1): $($printers[$i])" }
    $choice = 0
    if (-not [int]::TryParse((Read-Host 'Numero da impressora HP da loja'), [ref]$choice) -or $choice -lt 1 -or $choice -gt $printers.Count) {
        throw 'Impressora invalida. Instale o driver da HP e execute novamente.'
    }
    $desired = $printers[$choice - 1]
}

$candidates = @(
    "$env:LOCALAPPDATA\SumatraPDF\SumatraPDF.exe",
    "$env:ProgramFiles\SumatraPDF\SumatraPDF.exe",
    "${env:ProgramFiles(x86)}\SumatraPDF\SumatraPDF.exe"
)
$sumatra = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $sumatra) {
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Title = 'Selecione o SumatraPDF.exe instalado'
    $dialog.Filter = 'SumatraPDF|SumatraPDF.exe'
    if ($dialog.ShowDialog() -ne 'OK') { throw 'Selecione o SumatraPDF para continuar.' }
    $sumatra = $dialog.FileName
}

Write-Host "Destino: $desired | A4 | uma copia | frente unica"
Write-Host 'Use a credencial exclusiva do agente, nunca a senha do ERP ou chaves de IA.'
Write-Host 'Se ainda nao recebeu a credencial, pressione Enter para preparar sem conectar.'
$secret = Read-Host 'Credencial do agente' -AsSecureString
$config = @{
    server = 'https://erp-eleven-backend.onrender.com'
    printer = $desired
    sumatra = $sumatra
    token = if ($secret.Length -gt 0) { ConvertFrom-SecureString $secret } else { '' }
}
$config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'config.json') -Encoding UTF8
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Agente.ps1') -Destination $root -Force

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Eleven Impressao.lnk'))
$shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $root 'Agente.ps1') + '"'
$shortcut.WorkingDirectory = $root
$shortcut.Save()
Write-Host 'Preparado. O atalho Eleven Impressao foi criado na Area de Trabalho.'
Write-Host 'Nenhuma impressao foi enviada. Para parar o agente, feche sua janela.'
Write-Host 'Este programa nao inicia com o Windows automaticamente.'

