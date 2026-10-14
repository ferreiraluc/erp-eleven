# Durable local journal: once dispatch starts, never print that job automatically again.
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.Drawing
$root = $PSScriptRoot
$lockStream = $null
try {
    $lockStream = [IO.File]::Open((Join-Path $root 'agent.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
} catch { Write-Host 'O agente ja esta aberto. Feche esta janela.'; Read-Host; exit 1 }

. (Join-Path $root 'Impressao.ps1')

function Api($method, $path, $body = $null) {
    $options = @{
        Uri = ($script:config.server + '/api/printing/agent/' + $path)
        Method = $method
        Headers = @{ Authorization = 'Bearer ' + $script:token }
        TimeoutSec = 30
        MaximumRedirection = 0
        UseBasicParsing = $true
    }
    if ($null -ne $body) { $options.Body = ($body | ConvertTo-Json -Compress); $options.ContentType = 'application/json' }
    Invoke-RestMethod @options
}

function Acknowledge($path, $record) {
    Api 'POST' ("jobs/$($record.id)/result") @{ status = $record.status; diagnostic = $record.diagnostic } | Out-Null
    $record.acked = $true
    Save-Journal $path $record
}

function Process-Job($record, $recordPath, $pdf) {
    $download = {
        param($destination)
        Invoke-WebRequest -Uri ($config.server + "/api/printing/agent/jobs/$($record.id)/pdf") -Headers @{ Authorization = 'Bearer ' + $token } -OutFile $destination -UseBasicParsing -TimeoutSec 30 -MaximumRedirection 0
    }
    $preflight = {
        if ((Get-Service -Name Spooler).Status -ne 'Running') { throw 'Spooler parado' }
        if (@([Drawing.Printing.PrinterSettings]::InstalledPrinters) -notcontains $config.printer) { throw 'Fila ausente' }
        if (-not (Test-Path -LiteralPath $config.sumatra)) { throw 'Sumatra ausente' }
        if ($config.profile -eq 'tickets') {
            if ($record.profile -ne 'tickets') { throw 'Trabalho sem perfil de ticket.' }
            $printerSettings = New-Object Drawing.Printing.PrinterSettings
            $printerSettings.PrinterName = $config.printer
            $paper = $printerSettings.DefaultPageSettings.PaperSize
            if (-not (Test-TicketPaper $record $paper.Width $paper.Height)) {
                Write-Host "Papel diferente do ERP: configure no driver Zebra $($record.paper_width_mm) x $($record.paper_height_mm) mm."
                throw 'Tamanho de papel divergente.'
            }
        }
        if ($config.printer.Contains('"') -or $pdf.Contains('"')) { throw 'Configuracao invalida' }
    }
    $dispatch = {
        param($entry, $path, $document)
        $printSettings = Get-PrintSettings $config.profile
        $arguments = '-print-to "' + $config.printer + '" -print-settings "' + $printSettings + '" -silent "' + $document + '"'
        Invoke-Renderer $entry $path $config.sumatra $arguments
    }
    Invoke-PreparedPrint $record $recordPath $pdf $download $preflight $dispatch
    $reason = if ($record.diagnostic) { $record.diagnostic.code } else { 'agente_anterior' }
    Write-Host "$(Get-Date -Format 'HH:mm:ss') Trabalho $($record.id): $($record.status) | $reason"
    if ($record.status -eq 'uncertain') { Write-Host 'Confira a fila do Windows antes de pedir outra copia. O envio nao sera repetido.' }
    if ($record.status -eq 'failed') { Write-Host 'Falha antes do envio. Corrija a conexao/configuracao e solicite uma nova copia no ERP ou bot.' }
}

try {
    $script:config = Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw | ConvertFrom-Json
    if ($config.server -ne 'https://erp-eleven-backend.onrender.com') { throw 'Servidor nao autorizado.' }
    if (-not $config.token) { throw 'Instalado sem credencial. Execute Instalar.cmd quando receber a credencial exclusiva.' }
    if (-not (Test-Path -LiteralPath $config.sumatra)) { throw 'SumatraPDF nao encontrado. Execute Instalar.cmd novamente.' }
    if (@([Drawing.Printing.PrinterSettings]::InstalledPrinters) -notcontains $config.printer) { throw 'A impressora configurada nao esta instalada. Execute Instalar.cmd para selecionar a fila correta.' }
    $secure = ConvertTo-SecureString $config.token
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $script:token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    $journal = Join-Path $root 'journal'
    New-Item -ItemType Directory -Force -Path $journal | Out-Null
    $profile = if ($config.profile -eq 'tickets') { 'tickets' } else { 'documents' }
    Write-Host "Eleven Impressao | $($config.printer) | $profile"
    Write-Host 'Conectando ao ERP. Feche esta janela para parar.'
    $connected = $false
    while ($true) {
        try {
            if (-not $connected) {
                # Update only this credential's existing device; never create a second queue.
                $name = $config.printer.Substring(0, [Math]::Min(100, $config.printer.Length))
                $connection = Api 'POST' 'connect' @{ name = $name; profile = $profile }
                if ($profile -eq 'tickets') {
                    if ($connection.profile -ne 'tickets') { throw 'Servidor nao habilitado para tickets.' }
                    Write-Host "Papel ERP: $($connection.paper_width_mm) x $($connection.paper_height_mm) mm. Confira o mesmo tamanho no driver Zebra."
                }
                $connected = $true
                Write-Host 'Conectado. Destino atualizado no ERP e no bot.'
            }
            # Resume only preparation/download. Dispatch is never repeated after a restart.
            foreach ($file in Get-ChildItem -LiteralPath $journal -Filter '*.json') {
                $loaded = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
                $record = @{}; foreach ($property in $loaded.PSObject.Properties) { $record[$property.Name] = $property.Value }
                if (Test-OwnedRendererRunning $record) { throw 'Um processo anterior do Sumatra ainda esta ativo. Confira o Windows.' }
                $pdf = Join-Path $journal "$($record.id).pdf"
                if (-not $record.acked) {
                    Process-Job $record $file.FullName $pdf
                    Acknowledge $file.FullName $record
                }
                Remove-Item -LiteralPath $pdf -Force -ErrorAction SilentlyContinue
            }
            $job = Api 'POST' 'claim'
            if ($job) {
                $id = [Guid]::Parse($job.id).ToString()
                $recordPath = Join-Path $journal "$id.json"
                if (Test-Path -LiteralPath $recordPath) { throw 'Trabalho repetido recusado.' }
                $pdf = Join-Path $journal "$id.pdf"
                $record = @{ id = $id; status = 'preparing'; sha256 = $job.sha256; acked = $false; profile = $job.profile; paper_width_mm = $job.paper_width_mm; paper_height_mm = $job.paper_height_mm }
                Save-Journal $recordPath $record
                Process-Job $record $recordPath $pdf
                Acknowledge $recordPath $record
                if (-not (Test-OwnedRendererRunning $record)) {
                    Remove-Item -LiteralPath $pdf -Force -ErrorAction SilentlyContinue
                }
            }
            if ($profile -eq 'tickets') { Start-Sleep -Seconds 3 } else { Start-Sleep -Seconds 10 }
        } catch {
            Write-Host "$(Get-Date -Format 'HH:mm:ss') Fila pausada: confira a conexao com o ERP e se ha um Sumatra anterior travado. Nova verificacao em 30 segundos."
            Start-Sleep -Seconds 30
        }
    }
} catch { Write-Host $_.Exception.Message; Read-Host 'Pressione Enter para fechar' }
finally { if ($lockStream) { $lockStream.Dispose() }; $script:token = $null }
