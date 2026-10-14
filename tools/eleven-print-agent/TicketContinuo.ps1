# Windows 10+ PDF renderer + ZPL raster, only for the ZD220 203 dpi continuous roll.
# Dot-sourcing defines helpers for tests; it never opens the spooler or prints.
param([string]$Pdf, [string]$Printer, [int]$WidthMm, [int]$HeightMm)
$ErrorActionPreference = 'Stop'

function Initialize-TicketRaster {
    Add-Type -AssemblyName System.Drawing
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    if ('ElevenTicketRaster' -as [type]) { return }
    Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @'
using System;
using System.IO;
using System.Text;
using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.ComponentModel;
public static class ElevenTicketRaster {
    public static byte[] Zpl(byte[] png, int width, int height) {
        if (width < 400 || width > 832 || height < 400 || height > 7928)
            throw new ArgumentException("Formato de bobina invalido.");
        using (var stream = new MemoryStream(png))
        using (var image = new Bitmap(stream)) {
            if (image.Width != width || image.Height != height)
                throw new ArgumentException("PDF rasterizado com dimensoes diferentes.");
            var strideBytes = (width + 7) / 8;
            var bitmap = image.LockBits(new Rectangle(0,0,width,height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
            var row = new byte[width * 4];
            var packed = new byte[strideBytes * height];
            try {
                for (int y=0; y<height; y++) {
                    Marshal.Copy(IntPtr.Add(bitmap.Scan0, y*bitmap.Stride), row, 0, row.Length);
                    for (int x=0; x<width; x++) {
                        int i=x*4;
                        int luminance=(row[i]*114 + row[i+1]*587 + row[i+2]*299)/1000;
                        luminance=(luminance*row[i+3]+255*(255-row[i+3]))/255;
                        if (luminance < 180) packed[y*strideBytes+x/8] |= (byte)(128 >> (x%8));
                    }
                }
            } finally { image.UnlockBits(bitmap); }
            // One format, one copy. Set continuous media before the content length.
            // Do not save settings to flash, calibrate, clear queues or reset the device.
            var zpl=new StringBuilder("^XA^MNN^MMT^PW"+width+"^LL"+height+"^LH0,0^LT0^LS0^PON^PMN");
            // GF fields have bounded byte counts; strips remain inside the SAME receipt.
            int rowsPerStrip=60000/strideBytes;
            for (int y=0; y<height; y+=rowsPerStrip) {
                int count=Math.Min(rowsPerStrip,height-y)*strideBytes;
                zpl.Append("^FO0,").Append(y).Append("^GFA,").Append(count).Append(',').Append(count).Append(',').Append(strideBytes).Append(',');
                for (int i=y*strideBytes; i<y*strideBytes+count; i++) zpl.Append(packed[i].ToString("X2"));
                zpl.Append("^FS");
            }
            zpl.Append("^PQ1,0,1,N^XZ");
            return Encoding.ASCII.GetBytes(zpl.ToString());
        }
    }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    public class DocInfo { public string Name; public string Output; public string DataType="RAW"; }
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
        Check(OpenPrinter(printer,out handle,IntPtr.Zero));
        try {
            Check(StartDocPrinter(handle,1,new DocInfo { Name="ELEVEN - Ticket continuo" })>0);
            Check(StartPagePrinter(handle));
            int written;
            Check(WritePrinter(handle,bytes,bytes.Length,out written));
            if (written!=bytes.Length) throw new IOException("Envio parcial. Confira a fila antes de pedir outra copia.");
            Check(EndPagePrinter(handle));
            Check(EndDocPrinter(handle));
        } finally { ClosePrinter(handle); }
    }
}
'@
}

function Wait-TicketOperation($Operation, [Type]$ResultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}

function Wait-TicketAction($Action) {
    # PowerShell 5.1 cannot select the WinRT IAsyncAction overload automatically.
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction'
    } | Select-Object -First 1
    $task = $method.Invoke($null, @($Action))
    $task.Wait() # Do not emit Task<VoidTaskResult> into the PDF byte stream.
}

function Convert-TicketPdf([string]$Path, [int]$Width, [int]$Height) {
    if ($Width -lt 50 -or $Width -gt 104 -or $Height -lt 50 -or $Height -gt 991) { throw 'Dimensoes invalidas.' }
    Initialize-TicketRaster
    $fileType = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
    $pdfType = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType=WindowsRuntime]
    $file = Wait-TicketOperation ($fileType::GetFileFromPathAsync([IO.Path]::GetFullPath($Path))) $fileType
    $document = Wait-TicketOperation ($pdfType::LoadFromFileAsync($file)) $pdfType
    if ($document.PageCount -ne 1) { throw 'Bobina continua exige PDF de uma unica pagina. Atualize o ERP.' }
    $page = $document.GetPage(0)
    $stream = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime]::new()
    $memory = New-Object IO.MemoryStream
    try {
        if ([Math]::Abs($page.Size.Width * 25.4 / 96 - $Width) -gt 1 -or [Math]::Abs($page.Size.Height * 25.4 / 96 - $Height) -gt 1) { throw 'PDF e trabalho com tamanhos diferentes.' }
        $options = [Windows.Data.Pdf.PdfPageRenderOptions, Windows.Data.Pdf, ContentType=WindowsRuntime]::new()
        $options.DestinationWidth = [uint32]($Width * 8)
        $options.DestinationHeight = [uint32]($Height * 8)
        Wait-TicketAction ($page.RenderToStreamAsync($stream, $options))
        $stream.Seek(0)
        $readMethod = [System.IO.WindowsRuntimeStreamExtensions].GetMethods() | Where-Object {
            $_.Name -eq 'AsStream' -and $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq 'IRandomAccessStream'
        } | Select-Object -First 1
        $reader = $readMethod.Invoke($null, @($stream))
        try { $reader.CopyTo($memory) } finally { $reader.Dispose() }
        return ,([ElevenTicketRaster]::Zpl($memory.ToArray(), $Width*8, $Height*8))
    } finally { $page.Dispose(); $stream.Dispose(); $memory.Dispose() }
}

if ($MyInvocation.InvocationName -ne '.') {
    if (-not $Pdf -or -not $Printer) {
        Write-Host 'Arquivo auxiliar. Abra o atalho Eleven Tickets na Area de Trabalho.'
        Read-Host 'Pressione Enter para fechar'
        return
    }
    try {
        $bytes = Convert-TicketPdf $Pdf $WidthMm $HeightMm
        [ElevenTicketRaster]::Send($Printer, $bytes)
        exit 0 # Accepted by Windows; never claim physical delivery.
    } catch { Write-Error $_ -ErrorAction Continue; exit 1 }
}
