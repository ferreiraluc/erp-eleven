$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../Impressao.ps1')
. (Join-Path $PSScriptRoot '../Etiquetas.ps1')
function Assert($condition, $message) { if (-not $condition) { throw $message } }
$root = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $path = Join-Path $root 'journal.json'; $doc = Join-Path $root 'label.zpl'
    $bytes = [Text.Encoding]::ASCII.GetBytes('^XA^CI28^MNY^PW480^LL240^FO340,65^BQN,2,5^FDMA,INV-A7K4P2^FS^PQ1^XZ')
    [IO.File]::WriteAllBytes($doc, $bytes)
    $hash = (Get-FileHash $doc -Algorithm SHA256).Hash.ToLowerInvariant()
    $record = @{id='test'; status='preparing'; sha256=$hash; profile='product_labels'; paper_width_mm=60; paper_height_mm=30}
    Assert (Test-LabelDocument $record $doc) 'Valid ZPL rejected'
    $record.profile='tickets'; Assert (-not (Test-LabelDocument $record $doc)) 'Ticket reached label path'; $record.profile='product_labels'
    $script:sent=0
    $download = { param($file) [IO.File]::WriteAllBytes($file, $bytes) }
    $dispatch = { param($entry,$journal,$file)
        $saved=Get-Content $journal -Raw|ConvertFrom-Json
        Assert ($saved.status -eq 'started') 'Missing durable journal before dispatch'
        $script:sent++; Set-PrintOutcome $entry 'submitted' 'renderer_accepted'
    }
    # Printer/API offline before dispatch does not lose or duplicate the job.
    try { Invoke-PreparedLabel $record $path $doc { throw 'offline' } {} $dispatch } catch { }
    Assert ($record.status -eq 'preparing' -and $script:sent -eq 0) 'Download failure consumed job'
    Invoke-PreparedLabel $record $path $doc $download {} $dispatch
    Assert ($record.status -eq 'submitted' -and $script:sent -eq 1) 'Label not sent once'
    Invoke-PreparedLabel $record $path $doc $download {} $dispatch
    Assert ($script:sent -eq 1) 'Completed label replayed'
    $record.status='started'
    Invoke-PreparedLabel $record $path $doc $download {} $dispatch
    Assert ($record.status -eq 'uncertain' -and $script:sent -eq 1) 'Restart repeated uncertain label'
    $record.status='preparing'; $record.sha256='bad'
    Invoke-PreparedLabel $record $path $doc $download {} $dispatch
    Assert ($record.status -eq 'failed' -and $script:sent -eq 1) 'Corrupt label sent'
    Initialize-LabelWriter # Compile interop only; never call Send / Windows spooler.
    Assert ($null -ne ('ElevenLabelWriter' -as [type])) 'RAW helper did not compile'
    foreach ($file in @('AgenteEtiquetas.ps1','Etiquetas.ps1','Instalar.ps1')) {
        $tokens=$null; $errors=$null
        [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot "../$file"),[ref]$tokens,[ref]$errors)|Out-Null
        Assert ($errors.Count -eq 0) "Parse failed: $file"
    }
    Write-Host 'PASS: label isolation, integrity, offline retry, durable dispatch and uncertain recovery. No printing.'
} finally { Remove-Item -LiteralPath $root -Recurse -Force }
