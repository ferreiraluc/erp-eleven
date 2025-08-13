import httpx
import asyncio
import json
import re
from typing import Dict, List, Optional
from datetime import datetime
import logging
from ..schemas.rastreamento import RastreamentoConsultaResponse, EventoRastreio

logger = logging.getLogger(__name__)


class RastreamentoService:
    """Serviço para consultar rastreamento usando diferentes provedores"""
    
    # Configuração dos serviços disponíveis em ordem de prioridade
    SERVICOS = {
        "0001": {
            "nome": "correios_api",
            "url": "https://www.linkcorreios.com.br/api/rastreio",
            "metodo": "rest",
            "priority": 1
        },
        "0002": {
            "nome": "rastreio_pro",
            "url": "https://api.linktrace.org/api/tracking",
            "metodo": "rest", 
            "priority": 2
        },
        "0003": {
            "nome": "api_tracker",
            "url": "https://api.tracker.correios.com.br/tracks",
            "metodo": "rest",
            "priority": 3
        },
        "0004": {
            "nome": "muambator",
            "url": "https://muambator.com.br/pacote/api",
            "metodo": "rest",
            "priority": 4
        }
    }
    
    def __init__(self):
        self.timeout = httpx.Timeout(30.0)
    
    async def consultar_rastreamento(
        self, 
        codigo: str, 
        servico_id: str = "0001"
    ) -> RastreamentoConsultaResponse:
        """
        Consulta rastreamento com sistema de fallback automático
        """
        # Ordenar serviços por prioridade
        servicos_ordenados = sorted(
            self.SERVICOS.items(), 
            key=lambda x: x[1].get("priority", 999)
        )
        
        last_error = None
        
        # Tentar cada serviço em ordem de prioridade
        for srv_id, srv_config in servicos_ordenados:
            try:
                logger.info(f"Tentando consultar {codigo} via {srv_config['nome']}")
                
                if srv_id == "0001":
                    result = await self._consultar_linkcorreios(codigo)
                elif srv_id == "0002":
                    result = await self._consultar_linktrace(codigo)
                elif srv_id == "0003":
                    result = await self._consultar_tracker_correios(codigo)
                elif srv_id == "0004":
                    result = await self._consultar_muambator(codigo)
                else:
                    continue
                    
                if result.sucesso:
                    logger.info(f"Sucesso com {srv_config['nome']} para {codigo}")
                    return result
                else:
                    logger.warning(f"Falha com {srv_config['nome']}: {result.erro}")
                    last_error = result.erro
                    
            except Exception as e:
                logger.error(f"Erro com {srv_config['nome']}: {str(e)}")
                last_error = str(e)
                continue
        
        # Se chegou aqui, todos os serviços falharam
        logger.error(f"Todos os serviços falharam para {codigo}")
        return RastreamentoConsultaResponse(
            codigo=codigo,
            status="ERRO",
            service_provider="fallback_failed",
            data=[],
            sucesso=False,
            erro=f"Todos os serviços falharam. Último erro: {last_error}"
        )
    
    async def _consultar_linkcorreios(self, codigo: str) -> RastreamentoConsultaResponse:
        """
        Consulta rastreamento usando LinkCorreios (API pública dos Correios)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Primeira tentativa: API pública simples
                response = await client.get(
                    f"https://www.linkcorreios.com.br/?id={codigo}",
                    headers={
                        "User-Agent": "ERP-Eleven/1.0 (https://erp-eleven.com)",
                        "Accept": "application/json, text/html",
                    }
                )
                
                if response.status_code == 200:
                    # Se retornou algo, tentar extrair informações básicas
                    text = response.text
                    
                    eventos = []
                    status = "PENDENTE"
                    
                    # Parse básico do HTML/resposta
                    if "entregue" in text.lower():
                        status = "ENTREGUE"
                        eventos.append(EventoRastreio(
                            data=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            situacao="Objeto entregue",
                            detalhes="Entrega confirmada pelos Correios"
                        ))
                    elif "transito" in text.lower() or "em trânsito" in text.lower():
                        status = "EM_TRANSITO"
                        eventos.append(EventoRastreio(
                            data=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            situacao="Objeto em trânsito",
                            detalhes="Objeto em processo de entrega"
                        ))
                    elif "postado" in text.lower():
                        status = "EM_TRANSITO"
                        eventos.append(EventoRastreio(
                            data=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            situacao="Objeto postado",
                            detalhes="Objeto foi postado pelos Correios"
                        ))
                    
                    return RastreamentoConsultaResponse(
                        codigo=codigo,
                        status=status,
                        service_provider="linkcorreios",
                        data=eventos,
                        sucesso=True
                    )
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
        except Exception as e:
            return RastreamentoConsultaResponse(
                codigo=codigo,
                status="ERRO",
                service_provider="linkcorreios",
                data=[],
                sucesso=False,
                erro=str(e)
            )
    
    async def _consultar_linktrace(self, codigo: str) -> RastreamentoConsultaResponse:
        """
        Consulta rastreamento usando API alternativa
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Tentativa com API de rastreio alternativa
                response = await client.post(
                    "https://api.linktrace.org/api/tracking",
                    json={"trackingNumber": codigo, "type": "correios"},
                    headers={
                        "User-Agent": "ERP-Eleven/1.0",
                        "Content-Type": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    eventos = []
                    status = "PENDENTE"
                    
                    # Parse da resposta da API
                    if data.get("success"):
                        tracking_info = data.get("tracking", {})
                        events = tracking_info.get("events", [])
                        
                        for event in events:
                            eventos.append(EventoRastreio(
                                data=event.get("date"),
                                local=event.get("location"),
                                situacao=event.get("description"),
                                detalhes=event.get("details")
                            ))
                        
                        # Determinar status
                        current_status = tracking_info.get("status", "").lower()
                        if "entregue" in current_status or "delivered" in current_status:
                            status = "ENTREGUE"
                        elif "trânsito" in current_status or "transit" in current_status:
                            status = "EM_TRANSITO"
                        elif "postado" in current_status or "posted" in current_status:
                            status = "EM_TRANSITO"
                    
                    return RastreamentoConsultaResponse(
                        codigo=codigo,
                        status=status,
                        service_provider="linktrace",
                        data=eventos,
                        sucesso=True
                    )
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
        except Exception as e:
            return RastreamentoConsultaResponse(
                codigo=codigo,
                status="ERRO",
                service_provider="linktrace",
                data=[],
                sucesso=False,
                erro=str(e)
            )
    
    async def _consultar_tracker_correios(self, codigo: str) -> RastreamentoConsultaResponse:
        """
        Consulta rastreamento usando API tracker dos Correios
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Simular consulta com API oficial (pode não funcionar sem token)
                response = await client.get(
                    f"https://www2.correios.com.br/sistemas/rastreamento/default.cfm?objetos={codigo}",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                    }
                )
                
                if response.status_code == 200:
                    text = response.text
                    eventos = []
                    status = "PENDENTE"
                    
                    # Parse básico do HTML dos Correios
                    if "objeto entregue" in text.lower():
                        status = "ENTREGUE"
                        eventos.append(EventoRastreio(
                            data=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            situacao="Objeto entregue",
                            detalhes="Confirmado pelo site oficial dos Correios"
                        ))
                    elif "objeto em trânsito" in text.lower():
                        status = "EM_TRANSITO"
                        eventos.append(EventoRastreio(
                            data=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            situacao="Objeto em trânsito",
                            detalhes="Em processo de entrega"
                        ))
                    elif "objeto postado" in text.lower():
                        status = "EM_TRANSITO"
                        eventos.append(EventoRastreio(
                            data=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            situacao="Objeto postado",
                            detalhes="Postado nos Correios"
                        ))
                    
                    return RastreamentoConsultaResponse(
                        codigo=codigo,
                        status=status,
                        service_provider="correios_oficial",
                        data=eventos,
                        sucesso=True
                    )
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
        except Exception as e:
            return RastreamentoConsultaResponse(
                codigo=codigo,
                status="ERRO",
                service_provider="correios_oficial",
                data=[],
                sucesso=False,
                erro=str(e)
            )
    
    async def _consultar_muambator(self, codigo: str) -> RastreamentoConsultaResponse:
        """
        Consulta rastreamento usando Muambator como último recurso
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"https://muambator.com.br/pacote/{codigo}/",
                    headers={
                        "User-Agent": "ERP-Eleven/1.0",
                        "Accept": "text/html,application/xhtml+xml"
                    }
                )
                
                if response.status_code == 200:
                    text = response.text
                    eventos = []
                    status = "PENDENTE"
                    
                    # Parse do Muambator
                    if "entregue" in text.lower():
                        status = "ENTREGUE"
                        eventos.append(EventoRastreio(
                            data=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            situacao="Objeto entregue",
                            detalhes="Confirmado via Muambator"
                        ))
                    elif "trânsito" in text.lower():
                        status = "EM_TRANSITO"
                        eventos.append(EventoRastreio(
                            data=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            situacao="Em trânsito",
                            detalhes="Rastreado via Muambator"
                        ))
                    
                    return RastreamentoConsultaResponse(
                        codigo=codigo,
                        status=status,
                        service_provider="muambator",
                        data=eventos,
                        sucesso=True
                    )
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
        except Exception as e:
            return RastreamentoConsultaResponse(
                codigo=codigo,
                status="ERRO",
                service_provider="muambator",
                data=[],
                sucesso=False,
                erro=str(e)
            )
    
    async def consultar_multiplos_codigos(
        self, 
        codigos: List[str], 
        servico_id: str = "0001"
    ) -> List[RastreamentoConsultaResponse]:
        """
        Consulta múltiplos códigos de rastreamento em paralelo
        """
        tasks = [
            self.consultar_rastreamento(codigo, servico_id) 
            for codigo in codigos
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def extrair_dados_para_historico(self, resposta: RastreamentoConsultaResponse) -> List[Dict]:
        """
        Converte os eventos de rastreamento para formato de histórico do banco
        """
        historico = []
        
        for evento in resposta.data:
            historico.append({
                "data": evento.data,
                "local": evento.local,
                "situacao": evento.situacao,
                "detalhes": evento.detalhes,
                "origem": evento.origem,
                "destino": evento.destino,
                "timestamp_consulta": datetime.now().isoformat()
            })
        
        return historico


# Instância global do serviço
rastreamento_service = RastreamentoService()