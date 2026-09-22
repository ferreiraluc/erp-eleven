# Durable local journal: once dispatch starts, never print that job automatically again.
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type -AssemblyName System.Drawing
$root = $PSScriptRoot
$lockStream = $null
try {
    $lockStream = [IO.File]::Open((Join-Path $root 'agent.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
} catch { Write-Host 'O agente ja esta aberto. Feche esta janela.'; Read-Host; exit 1 }

function Save-Journal($path, $item) {
    $tmp = "$path.tmp"
    $json = $item | ConvertTo-Json -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $stream = [IO.File]::Open($tmp, 'Create', 'Write', 'None')
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    Move-Item -LiteralPath $tmp -Destination $path -Force
}

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
    Api 'POST' ("jobs/$($record.id)/result") @{ status = $record.status } | Out-Null
    $record.acked = $true
    Save-Journal $path $record
}

try {
    $script:config = Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw | ConvertFrom-Json
    if ($config.server -ne 'https://erp-eleven-backend.onrender.com') { throw 'Servidor nao autorizado.' }
    if (-not $config.token) { throw 'Instalado sem credencial. Execute Instalar.cmd quando receber a credencial exclusiva.' }
    if (-not (Test-Path -LiteralPath $config.sumatra)) { throw 'SumatraPDF nao encontrado. Execute Instalar.cmd novamente.' }
    if (@([Drawing.Printing.PrinterSettings]::InstalledPrinters) -notcontains $config.printer) { throw 'A impressora configurada nao esta instalada.' }
    $secure = ConvertTo-SecureString $config.token
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $script:token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    $journal = Join-Path $root 'journal'
    New-Item -ItemType Directory -Force -Path $journal | Out-Null
    Write-Host "Eleven Impressao | $($config.printer) | A4"
    Write-Host 'Conectando ao ERP. Feche esta janela para parar.'
    while ($true) {
        try {
            # Finish acknowledgements before accepting another job. Never repeat a print.
            foreach ($file in Get-ChildItem -LiteralPath $journal -Filter '*.json') {
                $record = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
                if (-not $record.acked) {
                    if ($record.status -eq 'started') { $record.status = 'uncertain'; Save-Journal $file.FullName $record }
                    Acknowledge $file.FullName $record
                    Remove-Item -LiteralPath (Join-Path $journal "$($record.id).pdf") -Force -ErrorAction SilentlyContinue
                }
            }
            $job = Api 'POST' 'claim'
            if ($job) {
                $id = [Guid]::Parse($job.id).ToString()
                $recordPath = Join-Path $journal "$id.json"
                if (Test-Path -LiteralPath $recordPath) { throw 'Trabalho repetido recusado.' }
                $pdf = Join-Path $journal "$id.pdf"
                $record = @{ id = $id; status = 'started'; acked = $false }
                # Persist before ANY interaction with the print renderer.
                Save-Journal $recordPath $record
                try {
                    Invoke-WebRequest -Uri ($config.server + "/api/printing/agent/jobs/$id/pdf") -Headers @{ Authorization = 'Bearer ' + $token } -OutFile $pdf -UseBasicParsing -TimeoutSec 30 -MaximumRedirection 0
                    if ((Get-Item -LiteralPath $pdf).Length -gt 5242880) { throw 'PDF muito grande.' }
                    if ((Get-FileHash -LiteralPath $pdf -Algorithm SHA256).Hash.ToLowerInvariant() -ne $job.sha256) { throw 'PDF corrompido.' }
                    if ($config.printer.Contains('"') -or $pdf.Contains('"')) { throw 'Configuracao invalida.' }
                    $arguments = '-print-to "' + $config.printer + '" -print-settings "paper=A4,shrink,simplex,monochrome,1x" -silent "' + $pdf + '"'
                    $process = Start-Process -FilePath $config.sumatra -ArgumentList $arguments -PassThru
                    if (-not $process.WaitForExit(120000)) {
                        $record.status = 'uncertain'
                    } elseif ($process.ExitCode -eq 0) {
                        $record.status = 'submitted'
                    } else { $record.status = 'uncertain' }
                } catch { $record.status = 'uncertain' }
                Save-Journal $recordPath $record
                Acknowledge $recordPath $record
                Remove-Item -LiteralPath $pdf -Force -ErrorAction SilentlyContinue
                Write-Host "$(Get-Date -Format 'HH:mm:ss') Trabalho $id : $($record.status)"
                if ($record.status -eq 'uncertain') {
                    Write-Host 'Confira a fila do Windows antes de pedir outra copia. O envio nao sera repetido.'
                }
            }
            Start-Sleep -Seconds 10
        } catch {
            Write-Host "$(Get-Date -Format 'HH:mm:ss') Sem conexao ou acesso ao ERP. Nova tentativa em 30 segundos."
            Start-Sleep -Seconds 30
        }
    }
} catch { Write-Host $_.Exception.Message; Read-Host 'Pressione Enter para fechar' }
finally { if ($lockStream) { $lockStream.Dispose() }; $script:token = $null }
