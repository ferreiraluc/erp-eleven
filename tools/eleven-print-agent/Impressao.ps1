# Core functions only: safe to load in tests without a printer or network.
if ($MyInvocation.InvocationName -ne '.') {
    Write-Host 'Este e um arquivo auxiliar; ele nao inicia o agente.'
    Write-Host 'Abra Eleven Tickets (Zebra) ou Eleven Impressao (A4) na Area de Trabalho.'
    Write-Host 'Se ainda nao instalou, extraia todo o ZIP e abra Instalar.cmd.'
    Read-Host 'Pressione Enter para fechar'
    return
}
$script:AgentVersion = '2026.10.14.3'

function Save-Journal($path, $item) {
    $tmp = "$path.tmp"
    $bytes = [Text.Encoding]::UTF8.GetBytes(($item | ConvertTo-Json -Depth 6 -Compress))
    $stream = [IO.File]::Open($tmp, 'Create', 'Write', 'None')
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    Move-Item -LiteralPath $tmp -Destination $path -Force
}

function Set-PrintOutcome($record, $status, $code, $duration = 0, $exitCode = $null) {
    $record.status = $status
    $record.diagnostic = @{
        code = $code; agent_version = $script:AgentVersion
        duration_ms = [Math]::Min(86400000, [Math]::Max(0, $duration)); exit_code = $exitCode
    }
}

function Test-OwnedRendererRunning($record) {
    if (-not $record.process_id -or -not $record.process_started_ticks) { return $false }
    try {
        $p = [Diagnostics.Process]::GetProcessById([int]$record.process_id)
        try { return (-not $p.HasExited -and $p.StartTime.ToUniversalTime().Ticks.ToString() -eq $record.process_started_ticks) }
        finally { $p.Dispose() }
    } catch [ArgumentException] { return $false }
    # Access denied must block, not assume an old process ended.
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
        $record.process_id = $p.Id
        $record.process_started_ticks = $p.StartTime.ToUniversalTime().Ticks.ToString()
        Save-Journal $recordPath $record
        if ($p.WaitForExit($timeoutMs)) {
            $exitCode = $p.ExitCode
            if ($exitCode -eq 0) { Set-PrintOutcome $record 'submitted' 'renderer_accepted' $watch.ElapsedMilliseconds $exitCode }
            else { Set-PrintOutcome $record 'uncertain' 'renderer_exit_error' $watch.ElapsedMilliseconds $exitCode }
        } else {
            # Stop only the process we launched. Never clear the Windows queue or kill other Sumatra windows.
            try { $p.Kill(); $p.WaitForExit(5000) | Out-Null } catch { }
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
