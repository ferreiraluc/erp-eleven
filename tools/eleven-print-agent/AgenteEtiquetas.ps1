# Windows USB/ZPL, product labels only. Durable claim and journal; no Sumatra.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$lockStream = $null
function LabelApi($method, $path, $body = $null) {
    $options = @{ Uri=($config.server+'/api/printing/agent/'+$path); Method=$method
        Headers=@{Authorization='Bearer '+$token}; TimeoutSec=30; MaximumRedirection=0; UseBasicParsing=$true }
    if ($null -ne $body) { $options.Body=($body|ConvertTo-Json -Compress); $options.ContentType='application/json' }
    Invoke-RestMethod @options
}
function Run-Label($record, $recordPath) {
    $document = Join-Path $journal "$($record.id).zpl"
    Assert-RendererStopped $record
    if (-not $record.acked) {
        $preflight = {
            if ((Get-Service Spooler).Status -ne 'Running') { throw 'Spooler parado' }
            if (@([Drawing.Printing.PrinterSettings]::InstalledPrinters) -notcontains $config.printer) { throw 'Fila ausente' }
        }
        $download = { param($file)
            Invoke-WebRequest -Uri ($config.server+"/api/printing/agent/jobs/$($record.id)/zpl") -Headers @{Authorization='Bearer '+$token} -OutFile $file -TimeoutSec 30 -MaximumRedirection 0 -UseBasicParsing
        }
        $dispatch = { param($entry, $path, $file)
            $command = "& '"+(Join-Path $root 'Etiquetas.ps1').Replace("'","''")+"' -Document '"+$file.Replace("'","''")+"' -Printer '"+$config.printer.Replace("'","''")+"'"
            $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
            Invoke-Renderer $entry $path "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $encoded"
        }
        $script:stage = 'process_job'
        Invoke-PreparedLabel $record $recordPath $document $download $preflight $dispatch
        $script:stage = 'acknowledge'
        LabelApi 'POST' "jobs/$($record.id)/result" @{status=$record.status; diagnostic=$record.diagnostic} | Out-Null
        $record.acked = $true
        Save-Journal $recordPath $record
        Write-Host "$(Get-Date -Format 'HH:mm:ss') Etiquetas $($record.id): $($record.status)"
        if ($record.status -eq 'uncertain') { Write-Host 'Confira o papel e o spooler. Este trabalho NAO sera repetido automaticamente.' }
    }
    Assert-RendererStopped $record
    Remove-Item -LiteralPath $document -Force -ErrorAction SilentlyContinue
}
try {
    . (Join-Path $root 'Impressao.ps1')
    . (Join-Path $root 'Etiquetas.ps1')
    $script:AgentVersion = '2026.10.21.1'
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Add-Type -AssemblyName System.Drawing
    $lockStream = [IO.File]::Open((Join-Path $root 'agent.lock'), 'OpenOrCreate', 'ReadWrite', 'None')
    $config = Get-Content -LiteralPath (Join-Path $root 'config.json') -Raw | ConvertFrom-Json
    if ($config.server -ne 'https://erp-eleven-backend.onrender.com' -or $config.profile -ne 'product_labels') { throw 'Use o instalador exclusivo Eleven Etiquetas.' }
    if (-not $config.token) { throw 'Informe a credencial em Instalar.cmd.' }
    $secure = ConvertTo-SecureString $config.token
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    $journal = Join-Path $root 'journal'
    New-Item -ItemType Directory -Path $journal -Force | Out-Null
    $claimPath = Join-Path $root 'claim.json'
    $processed = New-Object 'System.Collections.Generic.HashSet[string]'
    Write-Host "Eleven Etiquetas | $($config.printer) | 60 x 30 mm | agente $script:AgentVersion"
    Write-Host 'Use etiquetas com intervalo, uma por fileira. Feche o antigo Eleven Tickets da Zebra.'
    $connected = $false
    while ($true) {
        $record = $null
        try {
            $script:stage = 'connect'
            if (-not $connected) {
                LabelApi 'POST' 'connect' @{ name=$config.printer.Substring(0,[Math]::Min(100,$config.printer.Length)); profile='product_labels' } | Out-Null
                $connected = $true
                Write-Host 'Conectado ao ERP. Nenhum ticket ou endereco sera recebido neste perfil.'
            }
            $script:stage = 'journal_read'
            foreach ($file in Get-ChildItem -LiteralPath $journal -Filter '*.json') {
                if ($processed.Contains($file.FullName)) { continue }
                $loaded = Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json
                $record = @{}; foreach ($property in $loaded.PSObject.Properties) { $record[$property.Name]=$property.Value }
                # Crash after saving the response but before clearing claim.json.
                if (Test-Path -LiteralPath $claimPath) {
                    $pending = Get-Content -LiteralPath $claimPath -Raw | ConvertFrom-Json
                    if ($pending.key -eq $record.claim_key) { Remove-Item -LiteralPath $claimPath -Force }
                }
                Run-Label $record $file.FullName
                [void]$processed.Add($file.FullName)
            }
            $record = $null
            $script:stage = 'claim'
            if (-not (Test-Path -LiteralPath $claimPath)) { Save-Journal $claimPath @{key=[Guid]::NewGuid().ToString()} }
            $claim = Get-Content -LiteralPath $claimPath -Raw | ConvertFrom-Json
            $job = LabelApi 'POST' ("claim?product_labels=true&claim_key="+[Guid]::Parse($claim.key).ToString())
            if ($job) {
                $id = [Guid]::Parse($job.id).ToString()
                if ($job.profile -ne 'product_labels' -or $job.format -ne 'zpl') { throw 'Trabalho de outro perfil.' }
                $path = Join-Path $journal "$id.json"
                if (Test-Path -LiteralPath $path) { throw 'Trabalho repetido recusado; confira o diario.' }
                $record = @{ id=$id; claim_key=$claim.key; status='preparing'; acked=$false; sha256=$job.sha256
                    profile=$job.profile; paper_width_mm=$job.paper_width_mm; paper_height_mm=$job.paper_height_mm }
                Save-Journal $path $record
                Remove-Item -LiteralPath $claimPath -Force
                Run-Label $record $path
                [void]$processed.Add($path)
            } else { Remove-Item -LiteralPath $claimPath -Force }
            if (-not $job) { Start-Sleep -Seconds 3 }
        } catch {
            Write-AgentPause $root (Get-AgentPauseDiagnostic $_ $script:stage $record)
            Start-Sleep -Seconds 30
        }
    }
} catch { Write-Host $_.Exception.Message; Read-Host 'Pressione Enter para fechar' }
finally { if ($lockStream) { $lockStream.Dispose() }; $token=$null }
