$ErrorActionPreference = 'Stop'
. (Join-Path (Split-Path $PSScriptRoot -Parent) 'TicketContinuo.ps1')
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('eleven-roll-test-' + [Guid]::NewGuid())
New-Item -ItemType Directory -Path $testRoot | Out-Null

function New-TestPdf($Path, $PageCount = 1, $HeightMm = 120) {
    $height = ($HeightMm * 72 / 25.4).ToString('0.000', [Globalization.CultureInfo]::InvariantCulture)
    $kids = if ($PageCount -eq 2) { '3 0 R 5 0 R' } else { '3 0 R' }
    $objects = @('<< /Type /Catalog /Pages 2 0 R >>', "<< /Type /Pages /Kids [$kids] /Count $PageCount >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 226.772 $height] /Resources << >> /Contents 4 0 R >>")
    $content = '0 0 0 rg 10 10 20 20 re f'
    $objects += "<< /Length $($content.Length) >>`nstream`n$content`nendstream"
    if ($PageCount -eq 2) { $objects += $objects[2] }
    $pdf = "%PDF-1.4`n"
    $offsets = @()
    for ($i=0; $i -lt $objects.Count; $i++) { $offsets += $pdf.Length; $pdf += "$($i+1) 0 obj`n$($objects[$i])`nendobj`n" }
    $xref = $pdf.Length
    $pdf += "xref`n0 $($objects.Count+1)`n0000000000 65535 f `n"
    foreach ($offset in $offsets) { $pdf += $offset.ToString('0000000000') + " 00000 n `n" }
    $pdf += "trailer`n<< /Size $($objects.Count+1) /Root 1 0 R >>`nstartxref`n$xref`n%%EOF`n"
    [IO.File]::WriteAllText($Path, $pdf, [Text.Encoding]::ASCII)
}
try {
    # Real Windows PDF rasterization + ZPL encoding. NEVER call Send / the spooler.
    $pdf = Join-Path $testRoot 'continuous.pdf'
    New-TestPdf $pdf
    $bytes = Convert-TicketPdf $pdf 80 120
    $zpl = [Text.Encoding]::ASCII.GetString($bytes)
    if (-not $zpl.StartsWith('^XA^MNN^MMT^PW640^LL960') -or -not $zpl.EndsWith('^PQ1,0,1,N^XZ')) { throw 'Wrong media or copy count.' }
    if ([regex]::Matches($zpl, '\^XA').Count -ne 1 -or [regex]::Matches($zpl, '\^XZ').Count -ne 1) { throw 'Receipt divided into labels.' }
    $fields = [regex]::Matches($zpl, '\^FO0,(\d+)\^GFA,(\d+),(\d+),(\d+),([0-9A-F]+)\^FS')
    $rows = 0; $black = 0; $hex = New-Object Text.StringBuilder
    foreach ($field in $fields) {
        if ([int]$field.Groups[1].Value -ne $rows) { throw 'Missing or reordered raster rows.' }
        $count = [int]$field.Groups[2].Value; $rowBytes = [int]$field.Groups[4].Value
        if ($rowBytes -ne 80 -or $count -gt 60000 -or $field.Groups[3].Value -ne $field.Groups[2].Value -or $field.Groups[5].Value.Length -ne $count*2) { throw 'Bad GF byte counts.' }
        $rows += $count/$rowBytes
        $black += [regex]::Matches($field.Groups[5].Value, '[1-9A-F]').Count
        $hex.Append($field.Groups[5].Value) | Out-Null
    }
    if ($rows -ne 960 -or $black -lt 100) { throw 'Missing PDF content.' }
    # The fixture square is at the PDF's bottom-left: verify actual raster position,
    # not only byte count, so upside-down/mirrored tickets cannot pass this check.
    $pixels = $hex.ToString()
    $bottom = [Convert]::ToInt32($pixels.Substring((900*80+5)*2,2),16)
    $top = [Convert]::ToInt32($pixels.Substring((40*80+5)*2,2),16)
    if (($bottom -band 128) -eq 0 -or $top -ne 0) { throw 'Raster flipped or PDF drawing lost.' }
    # WinRT keeps a memory mapping until collection/process exit. Real jobs have
    # distinct GUID filenames and each renderer exits; fixtures must also be distinct.
    $longPdf = Join-Path $testRoot 'long.pdf'
    New-TestPdf $longPdf 1 991
    $long = [Text.Encoding]::ASCII.GetString((Convert-TicketPdf $longPdf 80 991))
    if ($long -notmatch '\^LL7928' -or [regex]::Matches($long, '\^XZ').Count -ne 1) { throw 'Long receipt split.' }
    $pagedPdf = Join-Path $testRoot 'paged.pdf'
    New-TestPdf $pagedPdf 2
    $rejected = $false
    try { Convert-TicketPdf $pagedPdf 80 120 | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw 'Must reject paginated PDFs before dispatch.' }
    $rejected = $false
    try { Convert-TicketPdf $pdf 60 120 | Out-Null } catch { $rejected = $true }
    if (-not $rejected) { throw 'Must reject different media dimensions.' }
    Write-Host 'PASS: native PDF render and continuous ZPL at 8 dots/mm; no printer opened, no print dispatched.'
} finally { Remove-Item -LiteralPath $testRoot -Recurse -Force }
