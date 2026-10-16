# Durable local journal: once dispatch starts, never print that job automatically again.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$lockStream = $null

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
    $script:stage = 'acknowledge'
    Api 'POST' ("jobs/$($record.id)/result") @{ status = $record.status; diagnostic = $record.diagnostic } | Out-Null
    $record.acked = $true
    $script:stage = 'journal_write'
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
            if ($record.paper_mode -eq 'continuous' -and -not (Test-Path -LiteralPath (Join-Path $root 'TicketContinuo.ps1'))) { throw 'Atualize o Eleven Tickets para bobina continua.' }
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
        if ($config.profile -eq 'tickets' -and $entry.paper_mode -eq 'continuous') {
            $helper = Join-Path $root 'TicketContinuo.ps1'
            # EncodedCommand avoids interpolating printer/file names into shell code.
            $command = "& '" + $helper.Replace("'", "''") + "' -Pdf '" + $document.Replace("'", "''") + "' -Printer '" + $config.printer.Replace("'", "''") + "' -WidthMm " + [int]$entry.paper_width_mm + ' -HeightMm ' + [int]$entry.paper_height_mm
            $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
            Invoke-Renderer $entry $path "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $encoded"
            return
        }
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
    if (-not (Test-Path -LiteralPath (Join-Path $root 'config.json') -PathType Leaf)) {
        throw 'Esta pasta nao tem a configuracao do agente. Abra o atalho Eleven Tickets (Zebra) ou Eleven Impressao (A4) na Area de Trabalho. Se o atalho nao existe, extraia todo o ZIP e execute Instalar.cmd.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $root 'Impressao.ps1') -PathType Leaf)) {
        throw 'Instalacao incompleta. Extraia todo o ZIP e execute Instalar.cmd novamente, mantendo a credencial existente.'
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Add-Type -AssemblyName System.Drawing
    try { $lockStream = [IO.File]::Open((Join-Path $root 'agent.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'O agente ja esta aberto ou a pasta esta sem permissao. Confira a outra janela; nao abra duas copias.' }
    . (Join-Path $root 'Impressao.ps1')
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
    Write-Host "Eleven Impressao | $($config.printer) | $profile | agente $script:AgentVersion"
    Write-Host 'Conectando ao ERP. Feche esta janela para parar.'
    $connected = $false
    $paused = $false
    while ($true) {
        $record = $null
        $script:stage = 'connect'
        try {
            if (-not $connected) {
                # Update only this credential's existing device; never create a second queue.
                $name = $config.printer.Substring(0, [Math]::Min(100, $config.printer.Length))
                $connection = Api 'POST' 'connect' @{ name = $name; profile = $profile }
                if ($profile -eq 'tickets') {
                    if ($connection.profile -ne 'tickets') { throw 'Servidor nao habilitado para tickets.' }
                    if ($connection.paper_height_mm -eq 0) { Write-Host "Papel ERP: bobina continua $($connection.paper_width_mm) mm | altura automatica | Zebra ZPL 203 dpi." }
                    else { Write-Host "Papel ERP: $($connection.paper_width_mm) x $($connection.paper_height_mm) mm. Confira o mesmo tamanho no driver Zebra." }
                }
                $connected = $true
                Write-Host 'Conectado. Destino atualizado no ERP e no bot.'
            }
            # Resume only preparation/download. Dispatch is never repeated after a restart.
            $script:stage = 'journal_read'
            foreach ($file in Get-ChildItem -LiteralPath $journal -Filter '*.json') {
                $record = $null
                $script:stage = 'journal_read'
                $loaded = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
                $record = @{}; foreach ($property in $loaded.PSObject.Properties) { $record[$property.Name] = $property.Value }
                $script:stage = 'renderer_check'
                Assert-RendererStopped $record
                $pdf = Join-Path $journal "$($record.id).pdf"
                if (-not $record.acked) {
                    $script:stage = 'resume_job'
                    Process-Job $record $file.FullName $pdf
                    Acknowledge $file.FullName $record
                }
                $script:stage = 'cleanup'
                Remove-Item -LiteralPath $pdf -Force -ErrorAction SilentlyContinue
            }
            $record = $null
            $script:stage = 'claim'
            $job = Api 'POST' 'claim?continuous_tickets=true'
            if ($job) {
                $id = [Guid]::Parse($job.id).ToString()
                $recordPath = Join-Path $journal "$id.json"
                if (Test-Path -LiteralPath $recordPath) { throw 'Trabalho repetido recusado.' }
                $pdf = Join-Path $journal "$id.pdf"
                $record = @{ id = $id; status = 'preparing'; sha256 = $job.sha256; acked = $false; profile = $job.profile; paper_mode = $job.paper_mode; paper_width_mm = $job.paper_width_mm; paper_height_mm = $job.paper_height_mm }
                $script:stage = 'journal_write'
                Save-Journal $recordPath $record
                $script:stage = 'process_job'
                Process-Job $record $recordPath $pdf
                Acknowledge $recordPath $record
                $script:stage = 'renderer_check'
                Assert-RendererStopped $record
                $script:stage = 'cleanup'
                Remove-Item -LiteralPath $pdf -Force -ErrorAction SilentlyContinue
            }
            if ($paused) { Write-Host "$(Get-Date -Format 'HH:mm:ss') Fila retomada. Trabalhos enviados nao foram repetidos."; $paused = $false }
            if ($profile -eq 'tickets') { Start-Sleep -Seconds 3 } else { Start-Sleep -Seconds 10 }
        } catch {
            $paused = $true
            Write-AgentPause $root (Get-AgentPauseDiagnostic $_ $script:stage $record)
            Start-Sleep -Seconds 30
        }
    }
} catch { Write-Host $_.Exception.Message; Read-Host 'Pressione Enter para fechar' }
finally { if ($lockStream) { $lockStream.Dispose() }; $script:token = $null }
