$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Instale somente no Windows da loja.' }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
. (Join-Path $PSScriptRoot 'Configuracao.ps1')
$root = Join-Path $env:LOCALAPPDATA 'ElevenPrint'
New-Item -ItemType Directory -Force -Path $root | Out-Null
$lockStream = $null
try {
    try { $lockStream = [IO.File]::Open((Join-Path $root 'agent.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'Feche o Eleven Impressao antes de atualizar a impressora. Aguarde o trabalho atual terminar.' }
    $configPath = Join-Path $root 'config.json'
    $existing = if (Test-Path -LiteralPath $configPath) { Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json } else { $null }
    $printers = @([System.Drawing.Printing.PrinterSettings]::InstalledPrinters)
    if (-not $printers.Count) { throw 'Nenhuma impressora instalada. Instale o driver da Samsung e teste um PDF no Windows.' }
    Write-Host 'Atualizacao para Samsung SL-M2035W. Selecione a fila que ja imprime no Windows.'
    Write-Host 'O nome do driver pode ser diferente do modelo escrito na impressora.'
    if ($existing) { Write-Host "Destino anterior: $($existing.printer)" }
    $suggested = Get-SuggestedPrinterIndex $printers
    for ($i = 0; $i -lt $printers.Count; $i++) { Write-Host "$($i + 1): $($printers[$i])" }
    $prompt = 'Numero da impressora da loja'
    if ($suggested -ge 0) { $prompt += " (Enter = $($suggested + 1))" }
    $answer = Read-Host $prompt
    $choice = 0
    if ([string]::IsNullOrWhiteSpace($answer) -and $suggested -ge 0) { $choice = $suggested + 1 }
    elseif (-not [int]::TryParse($answer, [ref]$choice)) { throw 'Selecione o numero de uma impressora instalada.' }
    if ($choice -lt 1 -or $choice -gt $printers.Count) { throw 'Impressora invalida. Execute novamente e confira a lista.' }
    $desired = $printers[$choice - 1]
    if ($desired.Contains('"')) { throw 'O nome da impressora nao pode conter aspas. Renomeie a fila no Windows.' }

    $candidates = @(
        $(if ($existing) { $existing.sumatra }),
        "$env:LOCALAPPDATA\SumatraPDF\SumatraPDF.exe",
        "$env:ProgramFiles\SumatraPDF\SumatraPDF.exe",
        "${env:ProgramFiles(x86)}\SumatraPDF\SumatraPDF.exe"
    )
    $sumatra = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1
    if (-not $sumatra) {
        $dialog = New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title = 'Selecione o SumatraPDF.exe instalado'
        $dialog.Filter = 'SumatraPDF|SumatraPDF.exe'
        if ($dialog.ShowDialog() -ne 'OK') { throw 'Selecione o SumatraPDF para continuar.' }
        $sumatra = $dialog.FileName
    }

    Write-Host "Destino: $desired | A4 | uma copia | frente unica"
    Write-Host 'Use somente a credencial exclusiva do agente, nunca a senha do ERP.'
    if ($existing -and $existing.token) { Write-Host 'Pressione Enter para MANTER a credencial atual, sem precisar digita-la novamente.' }
    else { Write-Host 'Sem credencial, Enter prepara o agente sem conectar.' }
    $secret = Read-Host 'Credencial do agente' -AsSecureString
    $config = @{
        server = 'https://erp-eleven-backend.onrender.com'
        printer = $desired
        sumatra = $sumatra
        token = Get-AgentToken $existing $secret
    }
    # Preserve the device identity and journal; upgrading must not replay jobs.
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'Agente.ps1') -Destination $root -Force
    Save-AgentConfig $configPath $config

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Eleven Impressao.lnk'))
    $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $root 'Agente.ps1') + '"'
    $shortcut.WorkingDirectory = $root
    $shortcut.Save()
    Write-Host 'Atualizado. Abra Eleven Impressao na Area de Trabalho para conectar.'
    Write-Host 'O nome da impressora sera atualizado no ERP ao conectar. O historico foi preservado.'
    Write-Host 'A instalacao nao imprime. Ao abrir o agente, trabalhos pendentes voltam a ser processados.'
    Write-Host 'Este programa nao inicia com o Windows automaticamente.'
} finally { if ($lockStream) { $lockStream.Dispose() } }
