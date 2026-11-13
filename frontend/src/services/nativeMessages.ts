import { uiLocale } from '@/i18n/uiText'

const messages = {
  openScanner: ['Abrir leitor', 'Abrir lector', 'Open scanner'],
  scanning: ['Leitor aberto. Aponte para o código.', 'Lector abierto. Apunte al código.', 'Scanner open. Point at the code.'],
  scanCancelled: ['Leitura cancelada. Você pode tentar novamente ou digitar o código.', 'Lectura cancelada. Puede volver a intentar o escribir el código.', 'Scan cancelled. Try again or enter the code.'],
  cameraDenied: ['Permita o acesso à câmera nas configurações do aparelho ou digite o código.', 'Permita el acceso a la cámara en los ajustes del dispositivo o escriba el código.', 'Allow camera access in device settings or enter the code.'],
  scannerFailed: ['Não foi possível abrir o leitor. Tente novamente ou digite o código.', 'No se pudo abrir el lector. Vuelva a intentar o escriba el código.', 'Could not open the scanner. Try again or enter the code.'],
  scannerBusy: ['Já existe uma leitura em andamento.', 'Ya hay una lectura en curso.', 'A scan is already in progress.'],
  scanInstructions: ['Aponte para o QR Code ou código de barras', 'Apunte al código QR o de barras', 'Point at the QR code or barcode'],
  cancel: ['Cancelar', 'Cancelar', 'Cancel'],
  torchOn: ['Apagar luz', 'Apagar luz', 'Turn light off'],
  torchOff: ['Acender luz', 'Encender luz', 'Turn light on'],
  pdfOptions: ['Opções do PDF', 'Opciones del PDF', 'PDF options'],
  pdfPreparingShare: ['Preparando arquivo…', 'Preparando archivo…', 'Preparing file…'],
  pdfHelp: ['Compartilhe o arquivo ou escolha onde salvá-lo nas opções do aparelho.', 'Comparta el archivo o elija dónde guardarlo en las opciones del dispositivo.', 'Share the file or choose where to save it in your device options.'],
  pdfOpened: ['Arquivo encaminhado às opções do aparelho.', 'Archivo enviado a las opciones del dispositivo.', 'File passed to your device options.'],
  pdfCancelled: ['Compartilhamento cancelado. O PDF continua disponível.', 'Envío cancelado. El PDF sigue disponible.', 'Sharing cancelled. The PDF is still available.'],
  pdfFailed: ['Não foi possível abrir as opções do PDF. Tente novamente.', 'No se pudieron abrir las opciones del PDF. Vuelva a intentar.', 'Could not open PDF options. Try again.'],
  pdfInvalid: ['O arquivo recebido não é um PDF completo. Prepare o documento novamente antes de enviar.', 'El archivo recibido no es un PDF completo. Prepare el documento de nuevo antes de enviarlo.', 'The received file is not a complete PDF. Prepare the document again before sharing.'],
  pdfTooLarge: ['O PDF ultrapassa o limite de 20 MB para compartilhar neste aparelho.', 'El PDF supera el límite de 20 MB para compartir en este dispositivo.', 'The PDF exceeds the 20 MB sharing limit on this device.'],
  pdfSession: ['Entre novamente no sistema e abra o PDF para compartilhar.', 'Inicie sesión de nuevo y abra el PDF para compartirlo.', 'Sign in again and open the PDF to share it.'],
  pdfBusy: ['Conclua o compartilhamento já aberto antes de enviar outro arquivo.', 'Finalice el envío abierto antes de enviar otro archivo.', 'Finish the open share dialog before sharing another file.'],
} as const

export type NativeMessage = keyof typeof messages
export function nativeText(key: NativeMessage): string {
  const locale = uiLocale()
  return messages[key][locale.startsWith('es') ? 1 : locale.startsWith('en') ? 2 : 0]
}
