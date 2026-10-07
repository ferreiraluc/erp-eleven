$ErrorActionPreference = 'Stop'
$source = Split-Path $PSScriptRoot -Parent
# Parse every script in Windows PowerShell 5.1, without running the printer loop.
foreach ($file in Get-ChildItem -LiteralPath $source -Filter '*.ps1') {
    $parseErrors = $null; $tokens = $null
    [Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
}
. (Join-Path $source 'Configuracao.ps1')
function Assert($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
Assert ((Get-SuggestedPrinterIndex @('HP antiga', 'Samsung SL-M2035W')) -eq 1) 'Samsung not suggested'
Assert ((Get-SuggestedPrinterIndex @('HP antiga')) -eq -1) 'Old printer must not be selected'
Assert ((Get-SuggestedPrinterIndex @('Samsung SL-M2035W', 'Samsung SL-M2035W (USB)')) -eq -1) 'Ambiguous printers must require selection'
Assert ((Get-SuggestedPrinterIndex @('Microsoft Print to PDF', 'Samsung M203x Series')) -eq -1) 'Different driver name requires manual selection'

$root = Join-Path ([IO.Path]::GetTempPath()) ('eleven-config-test-' + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $empty = New-Object Security.SecureString
    $secret = ConvertTo-SecureString 'test-only-not-a-real-agent-credential' -AsPlainText -Force
    $encrypted = Get-AgentToken $null $secret
    Assert ($encrypted -ne 'test-only-not-a-real-agent-credential') 'Credential must be encrypted'
    $old = @{ token = $encrypted; printer = 'HP antiga'; sumatra = 'C:\test\SumatraPDF.exe' }
    Assert ((Get-AgentToken $old $empty) -eq $encrypted) 'Enter must preserve credential'
    Assert ((Get-AgentToken $null $empty) -eq '') 'New installation without credential stays disconnected'
    $refused = $false
    try { Get-AgentToken @{token='invalid-dpapi-value'} $empty | Out-Null } catch { $refused = $true }
    Assert $refused 'Unreadable credentials must not be silently erased'

    $journal = Join-Path $root 'journal'
    New-Item -ItemType Directory -Path $journal | Out-Null
    $record = Join-Path $journal 'existing.json'
    '{"status":"uncertain","acked":false}' | Set-Content -LiteralPath $record
    $before = (Get-FileHash -LiteralPath $record).Hash
    $path = Join-Path $root 'config.json'
    Save-AgentConfig $path $old
    $new = @{token=(Get-AgentToken $old $empty);printer='Samsung SL-M2035W';sumatra=$old.sumatra}
    Save-AgentConfig $path $new
    $loaded = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    Assert ($loaded.printer -eq 'Samsung SL-M2035W') 'Printer not replaced'
    Assert ($loaded.token -eq $encrypted) 'Credential changed'
    Assert ((Get-Content -LiteralPath "$path.bak" -Raw | ConvertFrom-Json).printer -eq 'HP antiga') 'Backup missing'
    Assert ((Get-FileHash -LiteralPath $record).Hash -eq $before) 'Journal changed'
    # A second update must also retain a valid backup.
    Save-AgentConfig $path $new
    Assert ((Get-Content -LiteralPath "$path.bak" -Raw | ConvertFrom-Json).token -eq $encrypted) 'Backup rotation failed'
    Write-Host 'PASS: syntax, selection, DPAPI credential reuse, atomic config and journal preservation. No print dispatched.'
} finally { Remove-Item -LiteralPath $root -Recurse -Force }
