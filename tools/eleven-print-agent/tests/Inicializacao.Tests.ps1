$ErrorActionPreference = 'Stop'
$source = Split-Path $PSScriptRoot -Parent
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('eleven-startup-test-' + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $testRoot | Out-Null

# Run real entry scripts in a child Windows PowerShell 5.1 process, with no
# credential, installed configuration, network, spooler or renderer. Replace
# only the interactive prompt so failures can be checked without hanging CI.
function Invoke-StartupCheck([string]$ScriptPath, [string]$Expected) {
    $quoted = $ScriptPath.Replace("'", "''")
    $command = "function Read-Host { param(`$Prompt) Write-Output ('WAIT: ' + `$Prompt) }; & '$quoted'"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
    $process = New-Object Diagnostics.Process
    $process.StartInfo.FileName = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $process.StartInfo.Arguments = "-NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $encoded"
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.CreateNoWindow = $true
    try {
        $process.Start() | Out-Null
        $outputTask = $process.StandardOutput.ReadToEndAsync()
        $errorTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(15000)) { $process.Kill(); throw 'Startup check hung.' }
        $output = $outputTask.Result
        $errors = $errorTask.Result
        if ($process.ExitCode -ne 0) { throw "Startup check failed: $errors" }
        # EncodedCommand can emit Write-Host via the information stream (CLIXML).
        if (($output + $errors) -notlike "*$Expected*" -or $output -notlike '*WAIT:*') {
            throw "Startup must explain and wait: $output $errors"
        }
    } finally { $process.Dispose() }
}

try {
    foreach ($name in @('Agente.ps1', 'Instalar.ps1')) {
        Copy-Item -LiteralPath (Join-Path $source $name) -Destination $testRoot
    }
    Invoke-StartupCheck (Join-Path $testRoot 'Agente.ps1') 'Esta pasta nao tem a configuracao'
    Invoke-StartupCheck (Join-Path $testRoot 'Instalar.ps1') 'Pacote incompleto'
    '{}' | Set-Content -LiteralPath (Join-Path $testRoot 'config.json')
    Invoke-StartupCheck (Join-Path $testRoot 'Agente.ps1') 'Instalacao incompleta'
    Copy-Item -LiteralPath (Join-Path $source 'Impressao.ps1') -Destination $testRoot
    Invoke-StartupCheck (Join-Path $testRoot 'Impressao.ps1') 'arquivo auxiliar'
    if (Test-Path -LiteralPath (Join-Path $testRoot 'agent.lock')) { throw 'Invalid startup must not lock or process the queue.' }
    if (Test-Path -LiteralPath (Join-Path $testRoot 'journal')) { throw 'Invalid startup must not create jobs.' }
    Write-Host 'PASS: downloaded agent, incomplete install and helper explain how to open the installed shortcut. No print dispatched.'
} finally { Remove-Item -LiteralPath $testRoot -Recurse -Force }
