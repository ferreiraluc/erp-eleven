# Shared by the installer; never touches the print queue.
function Get-SuggestedPrinterIndex([string[]]$Printers) {
    $matchingIndexes = @()
    for ($i = 0; $i -lt $Printers.Count; $i++) {
        if ($Printers[$i] -match '(?i)(?:SL[- ]?)?M2035W\b') { $matchingIndexes += $i }
    }
    if ($matchingIndexes.Count -eq 1) { return [int]$matchingIndexes[0] }
    return -1
}

function Get-AgentToken($Existing, [Security.SecureString]$Secret) {
    if ($Secret.Length -gt 0) { return ConvertFrom-SecureString $Secret }
    if ($Existing -and $Existing.token) {
        # DPAPI credentials belong to this Windows user, not a different PC/account.
        try { $check = ConvertTo-SecureString $Existing.token; $check.Dispose() }
        catch { throw 'Credencial antiga nao pode ser lida por este usuario Windows. Informe a credencial exclusiva do agente.' }
        return $Existing.token
    }
    return ''
}

function Save-AgentConfig([string]$Path, $Config) {
    $tmp = "$Path.tmp"
    $Config | ConvertTo-Json | Set-Content -LiteralPath $tmp -Encoding UTF8
    if (Test-Path -LiteralPath $Path) {
        [IO.File]::Replace($tmp, $Path, "$Path.bak")
    } else { [IO.File]::Move($tmp, $Path) }
}
