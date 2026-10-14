param([Alias('Profile')][ValidateSet('documents', 'tickets')][string]$AgentProfile = 'documents')
$ErrorActionPreference = 'Stop'
$lockStream = $null
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Instale somente no Windows da loja.' }
    foreach ($required in @('Configuracao.ps1', 'Agente.ps1', 'Impressao.ps1')) {
        if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $required) -PathType Leaf)) {
            throw 'Pacote incompleto. Use Extrair tudo no ZIP e abra Instalar.cmd na pasta extraida.'
        }
    }
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    . (Join-Path $PSScriptRoot 'Configuracao.ps1')
    $folder = if ($AgentProfile -eq 'tickets') { 'ElevenPrintTickets' } else { 'ElevenPrint' }
    $shortcutName = if ($AgentProfile -eq 'tickets') { 'Eleven Tickets.lnk' } else { 'Eleven Impressao.lnk' }
    $root = Join-Path $env:LOCALAPPDATA $folder
    New-Item -ItemType Directory -Force -Path $root | Out-Null
    try { $lockStream = [IO.File]::Open((Join-Path $root 'agent.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw "Feche $shortcutName antes de atualizar. Aguarde o trabalho atual terminar." }
    $configPath = Join-Path $root 'config.json'
    $existing = if (Test-Path -LiteralPath $configPath) { Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json } else { $null }
    $printers = @([System.Drawing.Printing.PrinterSettings]::InstalledPrinters)
    if (-not $printers.Count) { throw 'Nenhuma impressora instalada. Instale o driver da impressora e teste um PDF no Windows.' }
    if ($AgentProfile -eq 'tickets') { Write-Host 'Tickets Zebra ZD220. Selecione a fila USB que imprime no Windows.' }
    else { Write-Host 'Atualizacao para Samsung SL-M2035W. Selecione a fila que ja imprime no Windows.' }
    Write-Host 'O nome do driver pode ser diferente do modelo escrito na impressora.'
    if ($existing) { Write-Host "Destino anterior: $($existing.printer)" }
    $suggested = Get-SuggestedPrinterIndex $printers $AgentProfile
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

    if ($AgentProfile -eq 'tickets') { Write-Host "Destino: $desired | Ticket no tamanho configurado no driver | uma copia"; Write-Host 'Ajuste o driver Zebra ao papel (60 x 80 mm inicialmente). Desative ajuste automatico de escala.' }
    else { Write-Host "Destino: $desired | A4 | uma copia | frente unica" }
    Write-Host 'Use somente a credencial exclusiva do agente, nunca a senha do ERP.'
    if ($existing -and $existing.token) { Write-Host 'Pressione Enter para MANTER a credencial atual, sem precisar digita-la novamente.' }
    else { Write-Host 'Sem credencial, Enter prepara o agente sem conectar.' }
    $secret = Read-Host 'Credencial do agente' -AsSecureString
    $config = @{
        profile = $AgentProfile
        server = 'https://erp-eleven-backend.onrender.com'
        printer = $desired
        sumatra = $sumatra
        token = Get-AgentToken $existing $secret
    }
    # Preserve the device identity and journal; upgrading must not replay jobs.
    foreach ($file in @('Agente.ps1', 'Impressao.ps1')) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination $root -Force
    }
    Save-AgentConfig $configPath $config

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) $shortcutName))
    $shortcut.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $shortcut.Arguments = '-NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File "' + (Join-Path $root 'Agente.ps1') + '"'
    $shortcut.WorkingDirectory = $root
    $shortcut.Save()
    Write-Host "Atualizado. Abra $shortcutName na Area de Trabalho para conectar."
    Write-Host 'Nao abra Agente.ps1 ou Impressao.ps1 na pasta do download. Use o atalho instalado.'
    Write-Host 'O nome da impressora sera atualizado no ERP ao conectar. O historico foi preservado.'
    Write-Host 'A instalacao nao imprime. Ao abrir o agente, trabalhos pendentes voltam a ser processados.'
    Write-Host 'Este programa nao inicia com o Windows automaticamente.'
} catch {
    Write-Host 'Nao foi possivel concluir a configuracao:' -ForegroundColor Red
    Write-Host $_.Exception.Message
    Read-Host 'Anote a mensagem acima. Pressione Enter para fechar'
} finally { if ($lockStream) { $lockStream.Dispose() } }
