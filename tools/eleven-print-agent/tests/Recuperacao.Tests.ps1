$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'Impressao.ps1')
function Assert($condition, $message) { if (-not $condition) { throw $message } }

# Reproduce PowerShell's suppressed .NET property-getter failure. This is a fake
# process: no credentials, spooler, Sumatra, protected process or network access.
if (-not ('ElevenRecoveryTestProcess' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
public sealed class ElevenRecoveryTestProcess : IDisposable {
    public bool Exited;
    public bool FailExit;
    public int FailStart;
    public bool Disposed;
    public DateTime Created = new DateTime(2026, 11, 9, 10, 0, 0, DateTimeKind.Utc).AddTicks(7);
    public bool HasExited { get { if (FailExit) throw new Win32Exception(5); return Exited; } }
    public DateTime StartTime { get {
        if (FailStart == -1) throw new InvalidOperationException("Synthetic process exited during inspection");
        if (FailStart != 0) throw new Win32Exception(FailStart);
        return Created;
    } }
    public void Dispose() { Disposed = true; }
}
'@
}
$probe = New-Object ElevenRecoveryTestProcess
$probe.FailStart = 5
$legacyFailure = $null
try { $probe.StartTime.ToUniversalTime() | Out-Null } catch { $legacyFailure = $_ }
Assert ($legacyFailure -and $legacyFailure.Exception.GetType().Name -eq 'RuntimeException') 'Missing reproduction of swallowed StartTime failure'
$record = @{id='d0fdbd00-5e5a-465f-9cea-968a6558f29a';status='uncertain';acked=$true;process_id=1684;process_started_ticks=$probe.Created.Ticks.ToString();diagnostic=@{code='agent_restarted'}}
$before = $record | ConvertTo-Json -Compress
$openProbe = { param($processNumber); Assert ($processNumber -eq 1684) 'Wrong renderer PID'; return $probe }
$sameIdentity = { param($processNumber); return @{Exists=$true;HasExited=$false;StartedTicks=[long]$probe.Created.Ticks} }
Assert (Test-OwnedRendererRunning $record $openProbe $sameIdentity) 'Same inaccessible renderer must still block'
Assert ($probe.Disposed) 'Failed .NET inspection leaked its process handle'
$reusedIdentity = { param($processNumber); return @{Exists=$true;HasExited=$false;StartedTicks=[long]$probe.Created.AddSeconds(1).Ticks} }
Assert (-not (Test-OwnedRendererRunning $record $openProbe $reusedIdentity)) 'Independent creation time must identify reused PID'
$exitedIdentity = { param($processNumber); return @{Exists=$true;HasExited=$true;StartedTicks=[long]$probe.Created.Ticks} }
Assert (-not (Test-OwnedRendererRunning $record $openProbe $exitedIdentity)) 'Proven exited renderer must not block'
$probe.FailStart = -1
Assert (-not (Test-OwnedRendererRunning $record $openProbe { return @{Exists=$false} })) 'Exit during StartTime read must recover safely'
$probe.FailExit = $true
Assert (Test-OwnedRendererRunning $record $openProbe $sameIdentity) 'HasExited getter failures must use independent identity too'
$denied = $null
try { Test-OwnedRendererRunning $record $openProbe { throw (New-Object ComponentModel.Win32Exception 5) } { return $null } | Out-Null } catch { $denied = $_ }
Assert ($null -ne $denied) 'Unknown/protected process must not be assumed stopped'
$diagnostic = Get-AgentPauseDiagnostic $denied 'renderer_check' $record
Assert ($diagnostic.code -eq 'renderer_check_failed' -and $diagnostic.windows_error -eq 5) 'Native access denial must retain safe numeric reason'
$nativeDenied = { throw (New-Object ComponentModel.Win32Exception 5) }
$cimReused = { param($number); return @{ProcessId=$number;CreationDate=$probe.Created.AddDays(1)} }
Assert (-not (Test-OwnedRendererRunning $record $openProbe $nativeDenied $cimReused)) 'CIM must release a positively identified reused protected PID'
$cimLocal = { param($number); return @{ProcessId=$number;CreationDate=$probe.Created.AddDays(1).ToLocalTime()} }
Assert (-not (Test-OwnedRendererRunning $record $openProbe $nativeDenied $cimLocal)) 'CIM local date must be compared in UTC'
$legacyTimeout = $record.Clone()
$legacyTimeout.process_started_ticks = [DateTime]::Parse('2020-01-02T17:00:04.7171796Z', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind).Ticks.ToString()
$legacyTimeout.diagnostic = @{code='renderer_timeout';duration_ms=120045;exit_code=$null}
$legacyBefore = $legacyTimeout | ConvertTo-Json -Compress
$incidentCim = { param($number); return @{ProcessId=$number;CreationDate=[DateTime]::Parse('2020-01-15T16:00:41.0000000Z', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind).ToLocalTime()} }
Assert (-not (Test-OwnedRendererRunning $legacyTimeout $openProbe $nativeDenied $incidentCim)) 'Old timeout must release a PID positively reused by a later process'
Assert (($legacyTimeout | ConvertTo-Json -Compress) -eq $legacyBefore) 'CIM recovery must preserve the acknowledged uncertain timeout without retrying it'
foreach ($difference in @([long]-10000000, [long]-9, [long]0, [long]9, [long]10000000)) {
    $query = { param($number); return @{ProcessId=$number;CreationDate=$probe.Created.AddTicks($difference)} }
    $blocked = $null
    try { Test-OwnedRendererRunning $record $openProbe $nativeDenied $query | Out-Null } catch { $blocked = $_ }
    Assert ($blocked -and (Get-AgentPauseDiagnostic $blocked 'renderer_check' $record).windows_error -eq 5) 'Same/nearby CIM timestamp must remain blocked with original Win32 code'
}
foreach ($difference in @([long]-10000001, [long]10000001)) {
    $query = { param($number); return @{ProcessId=$number;CreationDate=$probe.Created.AddTicks($difference)} }
    Assert (-not (Test-OwnedRendererRunning $record $openProbe $nativeDenied $query)) 'One-second boundary must use exact integer arithmetic'
}
foreach ($query in @(
    { return $null },
    { param($number); return @{ProcessId=$number;Name='svchost.exe'} },
    { param($number); return @{ProcessId=$number;CreationDate=$null} },
    { param($number); return @{ProcessId=$number;CreationDate=[DateTime]::MinValue} },
    { param($number); return @{ProcessId=$number;CreationDate=[DateTime]::SpecifyKind($probe.Created.AddDays(1), [DateTimeKind]::Unspecified)} },
    { param($number); return @{ProcessId=($number + 1);CreationDate=$probe.Created.AddDays(1)} },
    { param($number); return @(@{ProcessId=$number;CreationDate=$probe.Created}, @{ProcessId=$number;CreationDate=$probe.Created.AddDays(1)}) },
    { throw (New-Object TimeoutException 'Synthetic CIM timeout') },
    { throw (New-Object UnauthorizedAccessException 'Synthetic CIM denied') }
)) {
    $blocked = $null
    try { Test-OwnedRendererRunning $record $openProbe $nativeDenied $query | Out-Null } catch { $blocked = $_ }
    Assert ($blocked -and (Get-AgentPauseDiagnostic $blocked 'renderer_check' $record).windows_error -eq 5) 'Invalid/partial/failed CIM result must preserve native denial and block'
}
foreach ($unavailable in @({ return $null }, { return @{Exists=$true;HasExited=$false} })) {
    $failed = $false
    try { Test-OwnedRendererRunning $record $openProbe $unavailable | Out-Null } catch { $failed = $true }
    Assert ($failed) 'Incomplete independent inspection must fail closed'
}
$missingTicks = $record.Clone(); $missingTicks.Remove('process_started_ticks')
$probe.FailExit = $false; $probe.FailStart = 0; $probe.Exited = $false
$blocked = $false
try { Test-OwnedRendererRunning $missingTicks $openProbe $sameIdentity | Out-Null } catch { $blocked = $true }
Assert ($blocked) 'PID persisted without creation time must not release a live process'
$probe.Exited = $true
Assert (-not (Test-OwnedRendererRunning $missingTicks $openProbe { throw 'Native reader not needed' })) 'Confirmed exit may release a journal with missing creation time'
$probe.Exited = $false
Assert (-not (Test-OwnedRendererRunning $missingTicks $openProbe { return @{Exists=$false} })) 'Confirmed absence may release a journal with missing creation time'
$noProcess = $missingTicks.Clone(); $noProcess.Remove('process_id')
Assert (-not (Test-OwnedRendererRunning $noProcess { throw 'No process was recorded' })) 'Journal before process start must not inspect arbitrary processes'
Assert (($record | ConvertTo-Json -Compress) -eq $before) 'Renderer inspection must not rewrite uncertain status or acknowledge/reprint it'

# Use our own harmless test process to represent a reused PID. Never open the
# spooler, invoke Sumatra, contact the ERP or terminate a real printer process.
$self = [Diagnostics.Process]::GetCurrentProcess()
try {
    $native = Get-NativeRendererIdentity $self.Id
    Assert ($native.Exists -and -not $native.HasExited -and $native.StartedTicks -eq $self.get_StartTime().ToUniversalTime().Ticks) 'Limited native query must preserve exact 100ns process identity'
    Assert (-not (Get-NativeRendererIdentity ([int]::MaxValue)).Exists) 'Native query must identify a nonexistent PID'
    $cim = @(Get-CimRendererIdentity $self.Id)
    Assert ($cim.Count -eq 1 -and $cim[0].ProcessId -eq $self.Id -and $cim[0].CreationDate -is [DateTime]) 'Local CIM must identify the test process'
    Assert ($cim[0].CreationDate.Kind -in @([DateTimeKind]::Utc, [DateTimeKind]::Local)) 'Local CIM creation time must have an explicit time zone'
    Assert (-not (Test-CimRendererReused $self.Id $native.StartedTicks)) 'Real CIM precision must not mark the same running process as reused'
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
    $record.renderer_exited = $true
    Assert (-not (Test-OwnedRendererRunning $record)) 'Confirmed exit with error must not inspect a reused PID'
    Assert-RendererStopped $record
    $record.renderer_exited = $false
    Assert (Test-OwnedRendererRunning $record) 'Unconfirmed timeout must still block on its live renderer'
    $record.diagnostic = @{code='renderer_exit_error';exit_code=1}
    Assert (-not (Test-OwnedRendererRunning $record)) 'Legacy journal with a known exit code must not inspect reused PID'
    Assert ($record.status -eq 'uncertain') 'Process recovery must not change the print outcome'
    $record.diagnostic = @{code='renderer_timeout';exit_code=$null}
    Assert (Test-OwnedRendererRunning $record) 'Legacy timeout without confirmed exit must still block'
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

    # Lost claim responses, journal recovery and lost acknowledgements. No HTTP
    # request or renderer is used: these callbacks model the server boundaries.
    $journal = Join-Path $folder 'journal'
    New-Item -ItemType Directory -Path $journal | Out-Null
    $claimPath = Join-Path $folder 'claim.json'
    $script:claimKeys = New-Object 'Collections.Generic.List[string]'
    $script:job = @{id=[Guid]::NewGuid().ToString();sha256='synthetic'}
    $claim = {
        param($key)
        Assert ((Get-Content -LiteralPath $claimPath -Raw | ConvertFrom-Json).key -eq $key) 'Key must be durable before contacting ERP'
        $script:claimKeys.Add($key)
        if ($script:claimKeys.Count -eq 1) { throw 'Response lost after server accepted the claim' }
        return $script:job
    }
    $lost = $false
    try { Invoke-DurableClaim $claimPath $journal $claim | Out-Null } catch { $lost = $true }
    Assert ($lost -and (Test-Path -LiteralPath $claimPath)) 'Lost response discarded the recovery key'
    Assert (@(Get-ChildItem -LiteralPath $journal).Count -eq 0) 'Lost response invented a local job'
    $collected = Invoke-DurableClaim $claimPath $journal $claim
    Assert ($script:claimKeys.Count -eq 2 -and $script:claimKeys[0] -eq $script:claimKeys[1]) 'Retry claimed a different job'
    Assert ($collected.record.claim_key -eq $script:claimKeys[0]) 'Job must retain its recovery key'
    Assert ((Get-Content -LiteralPath $collected.path -Raw | ConvertFrom-Json).status -eq 'preparing') 'Claim not journaled before clearing key'
    Assert (-not (Test-Path -LiteralPath $claimPath)) 'Completed collection key not cleared'

    # Crash after durable job save, before clearing claim.json: never overwrite
    # the dispatch marker with preparing or repeat dispatch on resumed jobs.
    $collected.record.status = 'started'
    Save-Journal $collected.path $collected.record
    Save-Journal $claimPath @{key=$collected.record.claim_key}
    $resumed = Invoke-DurableClaim $claimPath $journal $claim
    Assert ($resumed.record.status -eq 'started') 'Recovery reset the dispatch marker'
    $script:dispatches = 0
    Invoke-PreparedPrint $resumed.record $resumed.path (Join-Path $journal 'unused.pdf') {} {} { $script:dispatches++ } {}
    Assert ($resumed.record.status -eq 'uncertain' -and $script:dispatches -eq 0) 'Recovered dispatch was printed twice'
    # A lost result response leaves a final status with acked=false. Retrying
    # recovery must still avoid dispatch, regardless of acknowledgement state.
    $resumed.record.status = 'submitted'
    Save-Journal $resumed.path $resumed.record
    Invoke-PreparedPrint $resumed.record $resumed.path (Join-Path $journal 'unused.pdf') {} {} { $script:dispatches++ } {}
    Assert ($script:dispatches -eq 0) 'Lost acknowledgement repeated dispatch'
    Save-Journal $claimPath @{key=$resumed.record.claim_key}
    Clear-JournalClaim $claimPath $resumed.record
    Assert (-not (Test-Path -LiteralPath $claimPath)) 'Startup did not clear matched journal claim'

    $empty = Invoke-DurableClaim $claimPath $journal { param($key); return $null }
    Assert ($null -eq $empty -and -not (Test-Path -LiteralPath $claimPath)) 'Empty queue left a stale claim'
    Save-Journal $claimPath @{key=[Guid]::NewGuid().ToString()}
    $mismatch = $false
    try { Invoke-DurableClaim $claimPath $journal { param($key); return $script:job } | Out-Null } catch { $mismatch = $true }
    Assert ($mismatch -and (Get-Content -LiteralPath $resumed.path -Raw | ConvertFrom-Json).status -eq 'submitted') 'Conflicting claim overwrote an existing journal'
    Save-Journal $claimPath @{key='invalid'}
    $invalid = $false; $script:invalidClaimCalls = 0
    try { Invoke-DurableClaim $claimPath $journal { $script:invalidClaimCalls++; throw 'Must not contact ERP' } | Out-Null } catch { $invalid = $true }
    Assert ($invalid -and $script:invalidClaimCalls -eq 0 -and (Test-Path -LiteralPath $claimPath)) 'Corrupt claim must fail closed before contacting ERP and remain recoverable'
    Write-Host 'PASS: PID reuse, active renderer guard, safe diagnostics, durable claim and lost acknowledgement recovery. No printing.'
} finally { Remove-Item -LiteralPath $folder -Recurse -Force }
