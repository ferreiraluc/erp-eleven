$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'Impressao.ps1')
function Assert($condition, $message) { if (-not $condition) { throw $message } }
Assert ((Get-PrintSettings '') -eq 'paper=A4,shrink,simplex,monochrome,1x') 'Legacy A4 settings changed'
Assert ((Get-PrintSettings 'documents') -eq (Get-PrintSettings '')) 'Document profile must preserve A4'
Assert ((Get-PrintSettings 'tickets') -eq 'noscale,simplex,monochrome,1x') 'Tickets must use driver media at actual size'
$ticket = @{ profile='tickets';paper_width_mm=60;paper_height_mm=80 }
Assert (Test-TicketPaper $ticket 236 315) '60x80 mm paper refused'
Assert (-not (Test-TicketPaper $ticket 315 236)) 'Rotated driver paper must be corrected explicitly'
Assert (-not (Test-TicketPaper $ticket 827 1169)) 'A4 must never accept receipt jobs'
Assert (Test-TicketPaper @{} 827 1169) 'Legacy A4 validation changed'
$roll = @{ profile='tickets';paper_width_mm=80;paper_height_mm=155;paper_mode='continuous' }
Assert (Test-TicketPaper $roll 236 315) 'Continuous ZPL must use per-job media, not old label defaults'
$roll.paper_height_mm=992
Assert (-not (Test-TicketPaper $roll 236 315)) 'ZD220 maximum length must be respected'
$folder = Join-Path ([IO.Path]::GetTempPath()) ('eleven-print-test-' + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $folder | Out-Null
try {
    $pdf = Join-Path $folder 'test.pdf'; $journal = Join-Path $folder 'test.json'
    [IO.File]::WriteAllText($pdf, '%PDF-1.4 test-only')
    $sha = (Get-FileHash $pdf -Algorithm SHA256).Hash.ToLowerInvariant()
    $script:downloads = 0; $script:dispatches = 0
    $download = { param($path); $script:downloads++; if ($script:downloads -lt 3) { throw 'Network unavailable' }; [IO.File]::WriteAllText($path, '%PDF-1.4 test-only') }
    $dispatch = {
        param($record, $path, $document)
        Assert ((Get-Content $path -Raw | ConvertFrom-Json).status -eq 'started') 'Dispatch must have durable started marker'
        $script:dispatches++
        Set-PrintOutcome $record 'submitted' 'renderer_accepted' 5 0
    }
    $record = @{id='test';status='preparing';sha256=$sha;acked=$false}
    Save-Journal $journal $record
    Invoke-PreparedPrint $record $journal $pdf $download {} $dispatch {}
    Assert ($record.status -eq 'submitted' -and $script:downloads -eq 3 -and $script:dispatches -eq 1) 'Download retry should dispatch exactly once'
    Invoke-PreparedPrint $record $journal $pdf $download {} $dispatch {}
    Assert ($script:dispatches -eq 1) 'Completed record repeated dispatch'

    $record = @{id='test';status='started';acked=$false}
    Invoke-PreparedPrint $record $journal $pdf $download {} $dispatch {}
    Assert ($record.status -eq 'uncertain' -and $record.diagnostic.code -eq 'agent_restarted') 'Legacy restart must stay uncertain'
    Assert ($script:dispatches -eq 1) 'Restart must never reprint'

    $record = @{id='test';status='preparing';sha256=$sha;acked=$false}
    Invoke-PreparedPrint $record $journal $pdf { throw 'Download unavailable' } {} $dispatch {}
    Assert ($record.status -eq 'failed' -and $record.diagnostic.code -eq 'download_failed') 'Pre-dispatch download failure is not uncertain'
    Assert ($script:dispatches -eq 1) 'Download failure dispatched'
    $record = @{id='test';status='preparing';sha256=$sha;acked=$false}
    Invoke-PreparedPrint $record $journal $pdf { param($path); [IO.File]::WriteAllText($path, '%PDF-changed') } {} $dispatch {}
    Assert ($record.diagnostic.code -eq 'invalid_pdf' -and $script:dispatches -eq 1) 'Invalid hash dispatched'

    $record = @{id='test';status='preparing';sha256=$sha;acked=$false}
    Invoke-PreparedPrint $record $journal $pdf $download { throw 'Spooler stopped' } $dispatch {}
    Assert ($record.status -eq 'failed' -and $record.diagnostic.code -eq 'printer_unavailable') 'Unavailable spooler dispatched'
    Assert ($script:dispatches -eq 1) 'Preflight failure dispatched'

    # Actual process handles, using harmless PowerShell children, never Sumatra or a printer.
    $exe = Join-Path $PSHOME 'powershell.exe'
    foreach ($code in @(0, 5)) {
        $record = @{id='test';status='started';acked=$false}
        Save-Journal $journal $record
        Invoke-Renderer $record $journal $exe ('-NoProfile -NonInteractive -Command "exit ' + $code + '"') 15000
        Assert ($record.diagnostic.exit_code -eq $code) 'Process handle did not retain the actual exit code'
        if ($code -eq 0) { Assert ($record.status -eq 'submitted') 'Exit 0 was reported as uncertain' }
        else { Assert ($record.status -eq 'uncertain') 'Renderer error must not be automatically retried' }
        Assert (-not (Test-OwnedRendererRunning $record)) 'Finished child detected as running'
    }
    $record = @{id='test';status='started';acked=$false}
    Invoke-Renderer $record $journal $exe '-NoProfile -NonInteractive -Command "Start-Sleep -Seconds 30"' 200
    Assert ($record.status -eq 'uncertain' -and $record.diagnostic.code -eq 'renderer_timeout') 'Timeout outcome missing'
    Assert (-not (Test-OwnedRendererRunning $record)) 'Timed-out child must be stopped'
    $record = @{id='test';status='started';acked=$false}
    Invoke-Renderer $record $journal (Join-Path $folder 'missing.exe') ''
    Assert ($record.status -eq 'failed' -and $record.diagnostic.code -eq 'renderer_start_failed') 'Failed launch should not be uncertain'
    Write-Host 'PASS: retries, PDF integrity, recovery, at-most-once, process exit codes and timeout. No print dispatched.'
} finally { Remove-Item -LiteralPath $folder -Force -Recurse }
