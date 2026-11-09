# Core functions only: safe to load in tests without a printer or network.
if ($MyInvocation.InvocationName -ne '.') {
    Write-Host 'Este e um arquivo auxiliar; ele nao inicia o agente.'
    Write-Host 'Abra Eleven Etiquetas, Eleven Tickets ou Eleven Impressao (A4) na Area de Trabalho.'
    Write-Host 'Se ainda nao instalou, extraia todo o ZIP e abra Instalar.cmd.'
    Read-Host 'Pressione Enter para fechar'
    return
}
$script:AgentVersion = '2026.11.09.2'

function Save-Journal($path, $item) {
    $tmp = "$path.tmp"
    $bytes = [Text.Encoding]::UTF8.GetBytes(($item | ConvertTo-Json -Depth 6 -Compress))
    $stream = [IO.File]::Open($tmp, 'Create', 'Write', 'None')
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    Move-Item -LiteralPath $tmp -Destination $path -Force
}

function Clear-JournalClaim($claimPath, $record) {
    # The job journal must already be durable before clearing the request key.
    # This also closes the crash window between those two filesystem operations.
    if ($record.claim_key -and (Test-Path -LiteralPath $claimPath)) {
        $claim = Get-Content -LiteralPath $claimPath -Raw | ConvertFrom-Json
        if ([Guid]::Parse([string]$claim.key).ToString() -eq $record.claim_key) {
            Remove-Item -LiteralPath $claimPath -Force
        }
    }
}

function Invoke-DurableClaim($claimPath, $journal, [scriptblock]$claim) {
    $script:stage = 'journal_write'
    if (-not (Test-Path -LiteralPath $claimPath)) {
        Save-Journal $claimPath @{ key = [Guid]::NewGuid().ToString() }
    }
    $script:stage = 'journal_read'
    $pending = Get-Content -LiteralPath $claimPath -Raw | ConvertFrom-Json
    $key = [Guid]::Parse([string]$pending.key).ToString()
    $script:stage = 'claim'
    # A timeout or dropped response keeps this key. The server returns the same
    # job on the next attempt, never a second job behind an invisible first one.
    $job = & $claim $key
    if (-not $job) {
        $script:stage = 'cleanup'
        Remove-Item -LiteralPath $claimPath -Force
        return $null
    }
    $id = [Guid]::Parse([string]$job.id).ToString()
    $path = Join-Path $journal "$id.json"
    $record = @{ id = $id; claim_key = $key; status = 'preparing'; sha256 = $job.sha256; acked = $false; profile = $job.profile; paper_mode = $job.paper_mode; paper_width_mm = $job.paper_width_mm; paper_height_mm = $job.paper_height_mm }
    if (Test-Path -LiteralPath $path) {
        $script:stage = 'journal_read'
        $loaded = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
        if ($loaded.id -ne $id -or $loaded.claim_key -ne $key) { throw 'Trabalho repetido recusado.' }
        # Never replace a started/final journal with a new preparing record.
        $record = @{}; foreach ($property in $loaded.PSObject.Properties) { $record[$property.Name] = $property.Value }
    } else {
        $script:stage = 'journal_write'
        Save-Journal $path $record
    }
    $script:stage = 'cleanup'
    Clear-JournalClaim $claimPath $record
    return @{ record = $record; path = $path }
}

function Set-PrintOutcome($record, $status, $code, $duration = 0, $exitCode = $null) {
    $record.status = $status
    $record.diagnostic = @{
        code = $code; agent_version = $script:AgentVersion
        duration_ms = [Math]::Min(86400000, [Math]::Max(0, $duration)); exit_code = $exitCode
    }
}

function Get-NativeRendererIdentity([int]$processNumber) {
    # .NET Framework Process.HasExited/StartTime can require more access than
    # this read-only query. Never open a terminate handle or inspect by PID alone.
    if (-not ('Eleven.RendererProcessProbe' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
namespace Eleven {
    public sealed class RendererProcessIdentity {
        public bool Exists { get; set; }
        public bool HasExited { get; set; }
        public long StartedTicks { get; set; }
    }
    public static class RendererProcessProbe {
        [StructLayout(LayoutKind.Sequential)]
        private struct FileTime { public uint Low; public uint High; }
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint access, bool inherit, int processId);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetProcessTimes(IntPtr process, out FileTime created, out FileTime exited, out FileTime kernel, out FileTime user);
        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetExitCodeProcess(IntPtr process, out uint code);
        [DllImport("kernel32.dll")]
        private static extern bool CloseHandle(IntPtr handle);
        private static long Value(FileTime value) { return ((long)value.High << 32) | value.Low; }
        public static RendererProcessIdentity Read(int processId) {
            if (processId <= 0) throw new ArgumentOutOfRangeException("processId");
            IntPtr handle = OpenProcess(0x1000, false, processId); // PROCESS_QUERY_LIMITED_INFORMATION
            if (handle == IntPtr.Zero) {
                int error = Marshal.GetLastWin32Error();
                // With a valid positive PID, ERROR_INVALID_PARAMETER means no
                // such process. Access denied/other errors prove nothing.
                if (error == 87) return new RendererProcessIdentity { Exists = false };
                throw new Win32Exception(error);
            }
            try {
                FileTime created, exited, kernel, user;
                if (!GetProcessTimes(handle, out created, out exited, out kernel, out user))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                if (Value(created) <= 0) throw new InvalidOperationException("Process creation time unavailable");
                uint exitCode;
                if (!GetExitCodeProcess(handle, out exitCode))
                    throw new Win32Exception(Marshal.GetLastWin32Error());
                return new RendererProcessIdentity {
                    // GetProcessTimes' exit timestamp is undefined while active.
                    // STILL_ACTIVE (259) is conservatively treated as running.
                    Exists = true, HasExited = exitCode != 259,
                    StartedTicks = DateTime.FromFileTimeUtc(Value(created)).Ticks
                };
            } finally { CloseHandle(handle); }
        }
    }
}
'@
    }
    return [Eleven.RendererProcessProbe]::Read($processNumber)
}

function Get-CimRendererIdentity([int]$processNumber) {
    # Local provider only; no executable paths, command lines or remote sessions.
    Get-CimInstance -ClassName Win32_Process -Filter "ProcessId = $processNumber" -Property ProcessId, CreationDate -OperationTimeoutSec 10 -ErrorAction Stop
}

function Test-CimRendererReused([int]$processNumber, [long]$expectedTicks,
    [scriptblock]$getCimIdentity = { param($number); Get-CimRendererIdentity $number }) {
    if ($processNumber -le 0 -or $expectedTicks -le 0 -or $expectedTicks -gt [DateTime]::MaxValue.Ticks) { return $false }
    try {
        $rows = @(& $getCimIdentity $processNumber)
        if ($rows.Count -ne 1) { return $false }
        $currentNumber = 0
        if (-not [int]::TryParse([string]$rows[0].ProcessId, [ref]$currentNumber) -or $currentNumber -ne $processNumber) { return $false }
        $created = $rows[0].CreationDate
        if ($created -isnot [DateTime] -or $created.Ticks -le 0 -or
            $created.Kind -notin @([DateTimeKind]::Utc, [DateTimeKind]::Local)) { return $false }
        $actualTicks = $created.ToUniversalTime().Ticks
        # CIM can discard fractional precision. Within one second the identity
        # remains ambiguous; only a larger difference proves this PID was reused.
        # Keep integer arithmetic: converting 100ns ticks to double loses bits.
        return ([Math]::Abs([long]($actualTicks - $expectedTicks)) -gt [TimeSpan]::TicksPerSecond)
    } catch { return $false }
    # Empty/partial/failed CIM queries do not prove a process has disappeared.
}

function Test-OwnedRendererRunning($record,
    [scriptblock]$getProcess = { param($processNumber); [Diagnostics.Process]::GetProcessById($processNumber) },
    [scriptblock]$getNativeIdentity = { param($processNumber); Get-NativeRendererIdentity $processNumber },
    [scriptblock]$getCimIdentity = { param($processNumber); Get-CimRendererIdentity $processNumber }) {
    # These outcomes prove the child exited or was never started. Windows can
    # reuse its old PID for an unrelated/protected process; do not inspect it.
    if ($record.status -in @('submitted', 'failed') -or $record.renderer_exited -eq $true) { return $false }
    # Older journals have no renderer_exited flag, but an exit-code diagnostic
    # is also written only after WaitForExit succeeds. Preserve their uncertainty.
    if ($record.diagnostic.code -eq 'renderer_exit_error' -and $null -ne $record.diagnostic.exit_code) { return $false }
    if (-not $record.process_id) { return $false }
    $processNumber = 0; $expectedTicks = [long]0
    if (-not [int]::TryParse([string]$record.process_id, [ref]$processNumber) -or $processNumber -le 0) {
        throw (New-Object InvalidOperationException 'Identidade do renderizador invalida no diario.')
    }
    if ($record.process_started_ticks -and (-not [long]::TryParse([string]$record.process_started_ticks, [ref]$expectedTicks) -or
        $expectedTicks -le 0 -or $expectedTicks -gt [DateTime]::MaxValue.Ticks)) {
        throw (New-Object InvalidOperationException 'Horario do renderizador invalido no diario.')
    }
    try {
        $p = & $getProcess $processNumber
        # PowerShell silently turns exceptions from property getters into null.
        # Explicit methods preserve Win32/exit errors for the safe fallback.
        try {
            if ($p.get_HasExited()) { return $false }
            if (-not $expectedTicks) { throw (New-Object InvalidOperationException 'Horario do renderizador ausente no diario.') }
            return ($p.get_StartTime().ToUniversalTime().Ticks -eq $expectedTicks)
        }
        finally { $p.Dispose() }
    } catch [ArgumentException] { return $false }
    catch {
        try { $identity = & $getNativeIdentity $processNumber }
        catch {
            $nativeFailure = $_
            if (Test-CimRendererReused $processNumber $expectedTicks $getCimIdentity) { return $false }
            # Preserve the original Win32 code even if CIM fails or has no date.
            throw $nativeFailure
        }
        if ($null -eq $identity -or $identity.Exists -isnot [bool]) {
            throw (New-Object InvalidOperationException 'Nao foi possivel confirmar a identidade do renderizador.')
        }
        if (-not $identity.Exists) { return $false }
        if ($identity.HasExited -isnot [bool]) {
            throw (New-Object InvalidOperationException 'Identidade incompleta do renderizador.')
        }
        if ($identity.HasExited) { return $false }
        if (-not $expectedTicks -or $identity.StartedTicks -isnot [long] -or $identity.StartedTicks -le 0) {
            throw (New-Object InvalidOperationException 'Horario do renderizador indisponivel; processo ainda ativo.')
        }
        return ($identity.StartedTicks -eq $expectedTicks)
    }
    # If every reader remains inconclusive, block. Never assume an old PID ended.
}

function Assert-RendererStopped($record) {
    if (Test-OwnedRendererRunning $record) {
        $exception = New-Object InvalidOperationException 'Renderizador anterior ainda ativo.'
        $exception.Data['ElevenPauseCode'] = 'renderer_active'
        throw $exception
    }
}

function Get-AgentPauseDiagnostic($failure, [string]$stage, $record) {
    $stages = @('connect', 'journal_read', 'journal_write', 'renderer_check', 'resume_job', 'acknowledge', 'claim', 'process_job', 'cleanup')
    if ($stage -notin $stages) { $stage = 'unknown' }
    $status = 0; $rendererActive = $false; $windowsError = 0; $exception = $failure.Exception
    # Read only typed metadata: never expose HTTP bodies, headers, token, document
    # contents, local paths or Exception.Message (which can contain any of those).
    for ($depth = 0; $exception -and $depth -lt 5; $depth++) {
        if ($exception.Data['ElevenPauseCode'] -eq 'renderer_active') { $rendererActive = $true }
        if ($exception -is [ComponentModel.Win32Exception]) { $windowsError = [int]$exception.NativeErrorCode }
        if ($exception.PSObject.Properties['Response'] -and $exception.Response) {
            try { $status = [int]$exception.Response.StatusCode } catch { }
        }
        $exception = $exception.InnerException
    }
    $code = 'agent_error'; $hint = 'Envie este diagnostico ao suporte. Nao apague journal nem solicite outra copia sem conferir o papel.'
    if ($rendererActive) { $code = 'renderer_active'; $hint = 'Um processo de impressao deste trabalho ainda esta ativo. Confira o processo e a fila do Windows antes de outra copia.' }
    elseif ($stage -eq 'renderer_check') {
        $code = 'renderer_check_failed'
        $hint = if ($windowsError -eq 5) { 'O Windows negou acesso ao processo anterior. Nenhum processo foi encerrado. Confira a fila e envie o diagnostico; nao apague o diario.' }
            else { 'Nao foi possivel confirmar se o renderizador anterior terminou. Confira a fila e envie o diagnostico; nao apague o diario para destravar.' }
    }
    elseif ($status -in @(401, 403)) { $code = 'credential_rejected'; $hint = 'O ERP recusou a credencial. Confira o perfil A4/Tickets/Etiquetas e a credencial no instalador; nao apague o diario.' }
    elseif ($status -eq 409 -and $stage -eq 'connect') { $code = 'profile_conflict'; $hint = 'A credencial nao corresponde ao perfil A4/Tickets/Etiquetas. Use o instalador do mesmo perfil.' }
    elseif ($status -eq 409) { $code = 'job_conflict'; $hint = 'O ERP recusou a operacao por conflito. Confira o trabalho no ERP e envie este diagnostico; nao reimprima nem apague o diario.' }
    elseif ($status -eq 429 -or $status -ge 500) { $code = 'erp_unavailable'; $hint = 'O ERP esta temporariamente indisponivel ou limitou as consultas. O agente tentara novamente, sem repetir impressao.' }
    elseif ($status -gt 0) { $code = 'erp_request_rejected'; $hint = 'O ERP recusou esta etapa. Envie o codigo HTTP e o trabalho ao suporte; preserve a configuracao e o diario.' }
    elseif ($stage -in @('connect', 'claim', 'acknowledge')) { $code = 'erp_connection_failed'; $hint = 'Nao foi possivel concluir a comunicacao com o ERP. Confira a internet; o agente tentara novamente sem repetir impressao.' }
    elseif ($stage -in @('journal_read', 'journal_write')) { $code = 'journal_unavailable'; $hint = 'Nao foi possivel ler ou salvar o diario local. Confira espaco/permissoes e envie o diagnostico; nao exclua journal.' }
    $jobId = ''; $parsed = [Guid]::Empty
    if ($record -and [Guid]::TryParse([string]$record.id, [ref]$parsed)) { $jobId = $parsed.ToString() }
    $processId = 0
    if ($record) { [int]::TryParse([string]$record.process_id, [ref]$processId) | Out-Null }
    $errorType = if ($failure.Exception) { $failure.Exception.GetType().Name } else { 'Unknown' }
    return @{ code=$code; hint=$hint; stage=$stage; http=$status; job=$jobId; process_id=[Math]::Max(0,$processId); windows_error=[Math]::Max(0,$windowsError); error_type=$errorType; agent_version=$script:AgentVersion }
}

function Write-AgentPause($folder, $diagnostic) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Fila pausada [$($diagnostic.code)] | etapa=$($diagnostic.stage) | HTTP=$($diagnostic.http) | trabalho=$($diagnostic.job) | PID=$($diagnostic.process_id) | Windows=$($diagnostic.windows_error) | erro=$($diagnostic.error_type) | agente=$($diagnostic.agent_version)"
    Write-Host $line
    Write-Host $diagnostic.hint
    Write-Host 'Nova verificacao em 30 segundos. Nenhum trabalho enviado sera reimpresso automaticamente.'
    try {
        $path = Join-Path $folder 'agente-diagnostico.log'
        if ((Test-Path -LiteralPath $path) -and (Get-Item -LiteralPath $path).Length -ge 65536) {
            Move-Item -LiteralPath $path -Destination "$path.1" -Force
        }
        [IO.File]::AppendAllText($path, ($line + [Environment]::NewLine + $diagnostic.hint + [Environment]::NewLine), [Text.Encoding]::UTF8)
    } catch { Write-Host 'Nao foi possivel gravar agente-diagnostico.log. Copie o diagnostico acima.' }
}

function Invoke-Renderer($record, $recordPath, $executable, $arguments, $timeoutMs = 120000) {
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $p = New-Object Diagnostics.Process
    $p.StartInfo = New-Object Diagnostics.ProcessStartInfo
    $p.StartInfo.FileName = $executable
    $p.StartInfo.Arguments = $arguments
    $p.StartInfo.UseShellExecute = $false
    $p.StartInfo.CreateNoWindow = $true
    $launched = $false
    try {
        # Preserve the process handle until ExitCode has been read (PowerShell 5.1).
        if (-not $p.Start()) { throw 'Renderer did not start' }
        $launched = $true
        $record.renderer_exited = $false
        $record.process_id = $p.get_Id()
        try { $record.process_started_ticks = $p.get_StartTime().ToUniversalTime().Ticks.ToString() }
        catch {
            $identity = Get-NativeRendererIdentity $record.process_id
            if (-not $identity.Exists) { throw 'Nao foi possivel identificar o renderizador iniciado.' }
            $record.process_started_ticks = $identity.StartedTicks.ToString()
        }
        Save-Journal $recordPath $record
        if ($p.WaitForExit($timeoutMs)) {
            $record.renderer_exited = $true
            $exitCode = $p.get_ExitCode()
            if ($exitCode -eq 0) { Set-PrintOutcome $record 'submitted' 'renderer_accepted' $watch.ElapsedMilliseconds $exitCode }
            else { Set-PrintOutcome $record 'uncertain' 'renderer_exit_error' $watch.ElapsedMilliseconds $exitCode }
        } else {
            # Stop only the process we launched. Never clear the Windows queue or kill other Sumatra windows.
            try { $p.Kill(); $record.renderer_exited = $p.WaitForExit(5000) } catch { }
            Set-PrintOutcome $record 'uncertain' 'renderer_timeout' $watch.ElapsedMilliseconds
        }
    } catch {
        if ($launched) { Set-PrintOutcome $record 'uncertain' 'renderer_interrupted' $watch.ElapsedMilliseconds }
        else { Set-PrintOutcome $record 'failed' 'renderer_start_failed' $watch.ElapsedMilliseconds }
    } finally { $p.Dispose(); $watch.Stop() }
}

function Invoke-PreparedPrint($record, $recordPath, $pdf, [scriptblock]$download, [scriptblock]$preflight, [scriptblock]$dispatch, [scriptblock]$retryDelay = { Start-Sleep -Seconds 3 }) {
    if ($record.status -eq 'started') {
        Set-PrintOutcome $record 'uncertain' 'agent_restarted'
        Save-Journal $recordPath $record
        return
    }
    if ($record.status -ne 'preparing') { return } # Completed jobs never dispatch again.
    $watch = [Diagnostics.Stopwatch]::StartNew()
    $valid = $false
    $failure = 'download_failed'
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Remove-Item -LiteralPath $pdf -Force -ErrorAction SilentlyContinue
            $failure = 'download_failed'
            & $download $pdf | Out-Null
            $failure = 'invalid_pdf'
            $length = (Get-Item -LiteralPath $pdf).Length
            if ($length -lt 5 -or $length -gt 5242880) { throw 'Invalid PDF size' }
            $stream = [IO.File]::OpenRead($pdf)
            try { $magic = New-Object byte[] 5; $stream.Read($magic, 0, 5) | Out-Null }
            finally { $stream.Dispose() }
            if ([Text.Encoding]::ASCII.GetString($magic) -ne '%PDF-') { throw 'Invalid PDF header' }
            if ((Get-FileHash -LiteralPath $pdf -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record.sha256) { throw 'Invalid PDF hash' }
            $valid = $true
            break
        } catch {
            if ($attempt -lt 3) { & $retryDelay | Out-Null }
        }
    }
    if (-not $valid) {
        Set-PrintOutcome $record 'failed' $failure $watch.ElapsedMilliseconds
        Save-Journal $recordPath $record
        return
    }
    try { & $preflight | Out-Null } catch {
        Set-PrintOutcome $record 'failed' 'printer_unavailable' $watch.ElapsedMilliseconds
        Save-Journal $recordPath $record
        return
    }
    # A crash from this point onward is uncertain, never automatically retried.
    $record.status = 'started'
    Save-Journal $recordPath $record
    try { & $dispatch $record $recordPath $pdf | Out-Null }
    catch { Set-PrintOutcome $record 'uncertain' 'renderer_interrupted' $watch.ElapsedMilliseconds }
    if ($record.status -eq 'started') { Set-PrintOutcome $record 'uncertain' 'renderer_interrupted' $watch.ElapsedMilliseconds }
    Save-Journal $recordPath $record
}

# Tickets use the media configured in the Zebra driver, at actual size.
function Get-PrintSettings([string]$Profile) {
    if ($Profile -eq 'tickets') { return 'noscale,simplex,monochrome,1x' }
    if ($Profile -and $Profile -ne 'documents') { throw 'Perfil de impressao invalido.' }
    return 'paper=A4,shrink,simplex,monochrome,1x'
}

function Test-TicketPaper($record, $paperWidthHundredths, $paperHeightHundredths) {
    if ($record.profile -ne 'tickets') { return $true }
    if (-not $record.paper_width_mm -or -not $record.paper_height_mm) { return $false }
    # Native ZPL carries its own width/length and continuous sensor mode, bypassing
    # the Windows driver's fixed-label pagination. Do not send this through Sumatra.
    if ($record.paper_mode -eq 'continuous') {
        return ($record.paper_width_mm -ge 50 -and $record.paper_width_mm -le 104 -and $record.paper_height_mm -ge 50 -and $record.paper_height_mm -le 991)
    }
    $width = $paperWidthHundredths * 0.254
    $height = $paperHeightHundredths * 0.254
    return ([Math]::Abs($width - $record.paper_width_mm) -le 1.5 -and [Math]::Abs($height - $record.paper_height_mm) -le 1.5)
}
