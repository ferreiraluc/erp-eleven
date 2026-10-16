$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'Impressao.ps1')
function Assert($condition, $message) { if (-not $condition) { throw $message } }

# Use our own harmless test process to represent a reused PID. Never open the
# spooler, invoke Sumatra, contact the ERP or terminate a real printer process.
$self = [Diagnostics.Process]::GetCurrentProcess()
try {
    $record = @{id='d0fdbd00-5e5a-465f-9cea-968a6558f29a'; process_id=$self.Id; process_started_ticks=$self.StartTime.ToUniversalTime().Ticks.ToString()}
    foreach ($status in @('submitted','failed')) {
        $record.status = $status
        Assert (-not (Test-OwnedRendererRunning $record)) 'Finished job must not inspect/reuse an unrelated live PID'
        Assert-RendererStopped $record
    }
    foreach ($status in @('started','uncertain')) {
        $record.status = $status
        Assert (Test-OwnedRendererRunning $record) 'Unresolved active renderer must continue blocking'
        $caught = $null
        try { Assert-RendererStopped $record } catch { $caught = $_ }
        Assert ($null -ne $caught) 'Active renderer did not block'
        $diagnostic = Get-AgentPauseDiagnostic $caught 'renderer_check' $record
        Assert ($diagnostic.code -eq 'renderer_active' -and $diagnostic.job -eq $record.id) 'Active renderer identity missing'
    }
    $record.process_started_ticks = '1'
    Assert (-not (Test-OwnedRendererRunning $record)) 'Different process creation time must not block'
    $record.process_id = [int]::MaxValue
    Assert (-not (Test-OwnedRendererRunning $record)) 'A process that ended must not block'
} finally { $self.Dispose() }

# Fake HTTP metadata only; secret-bearing exception bodies must never be logged.
$secret = 'Bearer TEST-SECRET-MUST-NOT-APPEAR customer@example.invalid C:\private\ticket.pdf'
foreach ($case in @(
    @{status=401;stage='acknowledge';expected='credential_rejected'},
    @{status=403;stage='claim';expected='credential_rejected'},
    @{status=409;stage='connect';expected='profile_conflict'},
    @{status=409;stage='acknowledge';expected='job_conflict'},
    @{status=404;stage='acknowledge';expected='erp_request_rejected'},
    @{status=422;stage='acknowledge';expected='erp_request_rejected'},
    @{status=429;stage='claim';expected='erp_unavailable'},
    @{status=503;stage='claim';expected='erp_unavailable'}
)) {
    $exception = New-Object Exception $secret
    $exception | Add-Member -NotePropertyName Response -NotePropertyValue ([pscustomobject]@{ StatusCode=$case.status })
    $failure = [pscustomobject]@{ Exception=$exception }
    $diagnostic = Get-AgentPauseDiagnostic $failure $case.stage @{}
    Assert ($diagnostic.code -eq $case.expected -and $diagnostic.http -eq $case.status) 'HTTP error not classified'
    Assert (($diagnostic | ConvertTo-Json -Compress) -notmatch 'TEST-SECRET|customer@|private') 'Sensitive error data leaked'
}
$failure = [pscustomobject]@{ Exception=(New-Object Exception $secret) }
Assert ((Get-AgentPauseDiagnostic $failure 'journal_read' @{}).code -eq 'journal_unavailable') 'Journal failure hidden'
Assert ((Get-AgentPauseDiagnostic $failure 'renderer_check' @{}).code -eq 'renderer_check_failed') 'Inspection failure must block'
Assert ((Get-AgentPauseDiagnostic $failure 'claim' @{}).code -eq 'erp_connection_failed') 'Network failure hidden'
$diagnostic = Get-AgentPauseDiagnostic $failure $secret @{id=$secret;process_id=$secret}
Assert ($diagnostic.stage -eq 'unknown' -and $diagnostic.job -eq '' -and $diagnostic.process_id -eq 0) 'Untrusted identity leaked'

$folder = Join-Path ([IO.Path]::GetTempPath()) ('eleven-recovery-test-' + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $folder | Out-Null
try {
    $path = Join-Path $folder 'agente-diagnostico.log'
    Write-AgentPause $folder $diagnostic
    $content = [IO.File]::ReadAllText($path)
    Assert ($content -match 'Fila pausada \[agent_error\]' -and $content -notmatch 'TEST-SECRET|customer@|private') 'Safe log missing or leaked secret'
    [IO.File]::WriteAllText($path, ('x' * 65536))
    Write-AgentPause $folder $diagnostic
    Assert ((Get-Item -LiteralPath "$path.1").Length -eq 65536) 'Bounded log did not rotate'
    Assert ((Get-Item -LiteralPath $path).Length -lt 4096) 'New log grew unexpectedly'
    Assert (-not (Test-Path (Join-Path $folder 'journal'))) 'Diagnostics must not change print journal'
    Write-Host 'PASS: finished PID reuse, active renderer guard, safe HTTP/local diagnostics and bounded log. No printing.'
} finally { Remove-Item -LiteralPath $folder -Recurse -Force }
