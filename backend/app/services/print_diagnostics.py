"""Bounded technical outcomes; never accept arbitrary logs or document contents."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class PrintDiagnostic(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: Literal['download_failed', 'invalid_pdf', 'printer_unavailable',
                  'renderer_start_failed', 'renderer_accepted', 'renderer_exit_error',
                  'renderer_timeout', 'renderer_interrupted', 'agent_restarted',
                  'network_accepted', 'network_interrupted', 'invalid_label', 'label_accepted', 'label_send_uncertain']
    agent_version: str = Field(pattern=r'^\d{4}\.\d{2}\.\d{2}\.\d{1,3}$')
    duration_ms: int = Field(default=0, ge=0, le=86400000)
    exit_code: int | None = Field(default=None, ge=-2147483648, le=2147483647)


MESSAGES = {
    'invalid_label': 'A etiqueta não passou na verificação de integridade. Nada foi enviado à impressora.',
    'label_accepted': 'Etiquetas aceitas pelo spooler do Windows. Confira a saída física na Zebra.',
    'label_send_uncertain': 'Envio de etiquetas incerto. Confira o papel e a fila do Windows antes de pedir outra cópia.',
    'document_generation_failed': 'Não foi possível montar o ticket. Nada foi enviado à impressora. Confira a venda antes de solicitar outra cópia.',
    'download_failed': 'O PDF não pôde ser baixado após três tentativas. Nada foi enviado à impressora.',
    'invalid_pdf': 'O PDF recebido não passou na verificação de integridade. Nada foi enviado à impressora.',
    'printer_unavailable': 'Confira a fila configurada, o serviço de impressão do Windows e o Sumatra. Nada foi enviado.',
    'renderer_start_failed': 'O Sumatra não iniciou. Nada foi enviado à impressora.',
    'renderer_accepted': 'O Sumatra aceitou o envio; isso não confirma a saída física do papel.',
    'renderer_exit_error': 'O Sumatra terminou com erro. Confira a fila do Windows antes de solicitar outra cópia.',
    'renderer_timeout': 'O Sumatra excedeu dois minutos. Confira a fila do Windows antes de solicitar outra cópia.',
    'renderer_interrupted': 'Houve uma interrupção após iniciar o envio. Confira a fila do Windows antes de solicitar outra cópia.',
    'agent_restarted': 'O agente reiniciou após iniciar o envio. Confira a fila do Windows antes de solicitar outra cópia.',
    'network_accepted': 'O ticket foi enviado à conexão da impressora. Confira o papel; o aceite TCP não comprova saída física.',
    'network_interrupted': 'O envio à impressora foi interrompido ou o agente reiniciou. Confira o papel antes de solicitar outra cópia; não houve reenvio automático.',
}


def diagnostic_message(job):
    diagnostic = job.diagnostic or {}
    if getattr(job, 'source', None) == 'product_labels' and diagnostic.get('code') == 'renderer_start_failed':
        return 'O processo de impressão não iniciou. Nenhuma etiqueta foi enviada.'
    return MESSAGES.get(diagnostic.get('code')) or (
        'O agente antigo não registrou o motivo. Confira a fila do Windows e atualize o agente.'
        if job.status in ('uncertain', 'failed') else None)
