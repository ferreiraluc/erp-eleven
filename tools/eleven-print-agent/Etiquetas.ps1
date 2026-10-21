# Dot-sourcing is safe: no printer/network access. Dedicated ZD220 ZPL path.
param([string]$Document, [string]$Printer)
$ErrorActionPreference = 'Stop'

function Initialize-LabelWriter {
    if ('ElevenLabelWriter' -as [type]) { return }
    Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.ComponentModel;
public static class ElevenLabelWriter {
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    public class DocInfo { public string Name="ELEVEN - Etiquetas de produtos"; public string Output; public string DataType="RAW"; }
    [DllImport("winspool.drv", EntryPoint="OpenPrinterW", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern bool OpenPrinter(string name, out IntPtr handle, IntPtr defaults);
    [DllImport("winspool.drv", EntryPoint="StartDocPrinterW", SetLastError=true, CharSet=CharSet.Unicode)]
    static extern int StartDocPrinter(IntPtr handle, int level, [In] DocInfo info);
    [DllImport("winspool.drv", SetLastError=true)] static extern bool StartPagePrinter(IntPtr handle);
    [DllImport("winspool.drv", SetLastError=true)] static extern bool WritePrinter(IntPtr handle, byte[] bytes, int count, out int written);
    [DllImport("winspool.drv", SetLastError=true)] static extern bool EndPagePrinter(IntPtr handle);
    [DllImport("winspool.drv", SetLastError=true)] static extern bool EndDocPrinter(IntPtr handle);
    [DllImport("winspool.drv", SetLastError=true)] static extern bool ClosePrinter(IntPtr handle);
    static void Check(bool ok) { if (!ok) throw new Win32Exception(Marshal.GetLastWin32Error()); }
    public static void Send(string printer, byte[] bytes) {
        IntPtr handle;
        Check(OpenPrinter(printer, out handle, IntPtr.Zero));
        try {
            Check(StartDocPrinter(handle, 1, new DocInfo()) > 0);
            Check(StartPagePrinter(handle));
            int written;
            Check(WritePrinter(handle, bytes, bytes.Length, out written));
            if (written != bytes.Length) throw new IOException("Envio parcial: confira a fila antes de outra copia.");
            Check(EndPagePrinter(handle));
            Check(EndDocPrinter(handle));
        } finally { ClosePrinter(handle); }
    }
}
'@
}

function Test-LabelDocument($record, [string]$path) {
    if ($record.profile -ne 'product_labels' -or $record.paper_width_mm -ne 60 -or $record.paper_height_mm -ne 30) { return $false }
    $length = (Get-Item -LiteralPath $path).Length
    if ($length -lt 30 -or $length -gt 32768) { return $false }
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $record.sha256) { return $false }
    $text = [IO.File]::ReadAllText($path, [Text.Encoding]::ASCII)
    return ($text.StartsWith('^XA^CI28^MNY') -and $text.EndsWith('^XZ') -and $text.Contains('^PW480^LL240'))
}

function Invoke-PreparedLabel($record, $path, $document, [scriptblock]$download, [scriptblock]$preflight, [scriptblock]$dispatch) {
    if ($record.status -eq 'started') {
        Set-PrintOutcome $record 'uncertain' 'agent_restarted'
        Save-Journal $path $record
        return
    }
    if ($record.status -ne 'preparing') { return }
    # Before dispatch, loss of network/printer availability leaves this local job
    # pending for another attempt; no second server job is claimed.
    & $preflight | Out-Null
    & $download $document | Out-Null
    if (-not (Test-LabelDocument $record $document)) {
        Set-PrintOutcome $record 'failed' 'invalid_label'
        Save-Journal $path $record
        return
    }
    $record.status = 'started'
    Save-Journal $path $record # Durable before the first possible spooler write.
    try { & $dispatch $record $path $document | Out-Null }
    catch { Set-PrintOutcome $record 'uncertain' 'label_send_uncertain' }
    if ($record.status -eq 'started') { Set-PrintOutcome $record 'uncertain' 'label_send_uncertain' }
    if ($record.status -eq 'submitted') { $record.diagnostic.code = 'label_accepted' }
    elseif ($record.status -eq 'uncertain') { $record.diagnostic.code = 'label_send_uncertain' }
    Save-Journal $path $record
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        $bytes = [IO.File]::ReadAllBytes($Document)
        if ($bytes.Length -lt 30 -or $bytes.Length -gt 32768) { throw 'Etiqueta invalida.' }
        Initialize-LabelWriter
        [ElevenLabelWriter]::Send($Printer, $bytes)
        exit 0
    } catch { exit 1 }
}
