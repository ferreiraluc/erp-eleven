"""
Serviço para importação de vendas via planilhas Excel do OneDrive
"""
import pandas as pd
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.orm import Session
from ..models.venda import Venda, MoedaTipo, PagamentoMetodo
from ..models.vendedor import Vendedor
from ..config import settings
import logging

logger = logging.getLogger(__name__)

class ExcelImportService:
    """Serviço para importar vendas de planilhas Excel"""
    
    def __init__(self, db: Session):
        self.db = db
        self.onedrive_access_token = None
    
    def authenticate_onedrive(self, access_token: str) -> bool:
        """Autentica com OneDrive usando access token"""
        try:
            # Testar se o token é válido
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get(
                'https://graph.microsoft.com/v1.0/me', 
                headers=headers
            )
            
            if response.status_code == 200:
                self.onedrive_access_token = access_token
                return True
            return False
        except Exception as e:
            logger.error(f"Erro na autenticação OneDrive: {e}")
            return False
    
    def download_excel_from_onedrive(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Baixa e lê planilha Excel do OneDrive
        
        Args:
            file_path: Caminho do arquivo no OneDrive (ex: /Vendas/2025/Janeiro.xlsx)
        
        Returns:
            DataFrame com os dados da planilha ou None se erro
        """
        if not self.onedrive_access_token:
            logger.error("Token OneDrive não configurado")
            return None
        
        try:
            headers = {'Authorization': f'Bearer {self.onedrive_access_token}'}
            
            # Construir URL para download do arquivo
            file_url = f'https://graph.microsoft.com/v1.0/me/drive/root:{file_path}:/content'
            
            response = requests.get(file_url, headers=headers)
            
            if response.status_code == 200:
                # Ler Excel diretamente dos bytes
                df = pd.read_excel(response.content, engine='openpyxl')
                logger.info(f"Planilha baixada com sucesso: {len(df)} linhas")
                return df
            else:
                logger.error(f"Erro ao baixar arquivo: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao processar planilha OneDrive: {e}")
            return None
    
    def read_local_excel(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Lê planilha Excel local (para testes)
        
        Args:
            file_path: Caminho local do arquivo Excel
            
        Returns:
            DataFrame com os dados da planilha ou None se erro
        """
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
            logger.info(f"Planilha local lida com sucesso: {len(df)} linhas")
            return df
        except Exception as e:
            logger.error(f"Erro ao ler planilha local: {e}")
            return None
    
    def validate_excel_structure(self, df: pd.DataFrame, cell_mapping: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Valida a estrutura da planilha usando mapeamento de células ou colunas
        
        Args:
            df: DataFrame da planilha
            cell_mapping: Dicionário com mapeamento de células (ex: {'vendedor': 'D11', 'moeda': 'B11'})
        """
        if cell_mapping:
            # Modo de mapeamento por células específicas
            return {
                'valid': True,
                'mapping_mode': 'cells',
                'cell_mapping': cell_mapping,
                'total_rows': len(df),
                'sheet_dimensions': df.shape
            }
        else:
            # Modo tradicional por colunas
            required_columns = ['vendedor', 'data_venda', 'valor_bruto', 'moeda', 'metodo_pagamento']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    'valid': False,
                    'error': f'Colunas obrigatórias ausentes: {", ".join(missing_columns)}',
                    'missing_columns': missing_columns
                }
            
            return {
                'valid': True,
                'mapping_mode': 'columns',
                'required_columns': required_columns,
                'total_rows': len(df)
            }
    
    def process_weekly_sales_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Processa dados semanais da planilha usando o novo mapeamento
        
        Estrutura da planilha:
        - D2=Junior, E2=Denis, F2=Sol, G2=Wiss, H2=Lucas (vendedores)
        - C3=G$, C4=EUR, C5=R$, C6=U$ (moedas)  
        - Dados nas interseções (ex: D3 = vendas do Junior em G$)
        
        Returns:
            Dict com vendas semanais processadas
        """
        try:
            processed_sales = []
            errors = []
            vendedor_cache = {}
            
            # Mapeamento fixo baseado na estrutura da planilha
            vendedores_map = {
                'D': ('Junior', 3),   # Coluna D, índice 3
                'E': ('Denis', 4),    # Coluna E, índice 4
                'F': ('Sol', 5),      # Coluna F, índice 5
                'G': ('Wiss', 6),     # Coluna G, índice 6
                'H': ('Lucas', 7)     # Coluna H, índice 7
            }
            
            moedas_map = {
                2: 'G$',    # Linha 3 (índice 2) = G$
                3: 'EUR',   # Linha 4 (índice 3) = EUR
                4: 'R$',    # Linha 5 (índice 4) = R$
                5: 'U$'     # Linha 6 (índice 5) = U$
            }
            
            logger.info(f"Processando dados semanais - planilha com {len(df)} linhas e {len(df.columns)} colunas")
            
            # Processar cada combinação vendedor x moeda
            for col_letter, (vendedor_nome, col_idx) in vendedores_map.items():
                # Verificar/buscar vendedor no cache
                if vendedor_nome not in vendedor_cache:
                    vendedor = self.db.query(Vendedor).filter(
                        Vendedor.nome.ilike(f'%{vendedor_nome}%'),
                        Vendedor.ativo == True
                    ).first()
                    vendedor_cache[vendedor_nome] = vendedor
                    
                    if not vendedor:
                        errors.append(f"Vendedor '{vendedor_nome}' não encontrado no sistema")
                        continue
                else:
                    vendedor = vendedor_cache[vendedor_nome]
                
                # Processar cada moeda para este vendedor
                for row_idx, moeda_str in moedas_map.items():
                    try:
                        if col_idx >= len(df.columns) or row_idx >= len(df):
                            logger.warning(f"Célula {col_letter}{row_idx+1} fora dos limites da planilha")
                            continue
                            
                        # Obter valor da célula
                        valor_raw = df.iloc[row_idx, col_idx]
                        logger.info(f"Célula {col_letter}{row_idx+1} ({vendedor_nome} - {moeda_str}): {valor_raw}")
                        
                        # Verificar se há valor válido
                        if pd.isna(valor_raw) or valor_raw == 0:
                            continue
                            
                        valor_bruto = self._parse_decimal(valor_raw)
                        if valor_bruto is None or valor_bruto <= 0:
                            logger.warning(f"Valor inválido para {vendedor_nome} - {moeda_str}: {valor_raw}")
                            continue
                        
                        # Processar moeda
                        moeda = self._parse_moeda(moeda_str)
                        if not moeda:
                            logger.error(f"Moeda não reconhecida: {moeda_str}")
                            continue
                        
                        # Criar registro de venda semanal
                        # Para dados semanais, usar data de hoje como referência
                        from datetime import date
                        today = date.today()
                        
                        sale_record = {
                            'vendedor_id': vendedor.id,
                            'vendedor_nome': vendedor.nome,
                            'data_venda': today,
                            'valor_bruto': valor_bruto,
                            'moeda': moeda,
                            'metodo_pagamento': PagamentoMetodo.PIX_POWER,  # Default para resumo semanal
                            'descricao_produto': f'Vendas semanais - {moeda_str}',
                            'observacoes': f'Resumo semanal extraído da célula {col_letter}{row_idx+1}',
                            'row_number': row_idx + 1,
                            'cell_reference': f'{col_letter}{row_idx+1}'
                        }
                        
                        processed_sales.append(sale_record)
                        logger.info(f"Venda processada: {vendedor_nome} - {moeda_str} - {valor_bruto}")
                        
                    except Exception as e:
                        error_msg = f"Erro ao processar célula {col_letter}{row_idx+1} ({vendedor_nome} - {moeda_str}): {str(e)}"
                        errors.append(error_msg)
                        logger.error(error_msg)
            
            logger.info(f"Processamento semanal concluído: {len(processed_sales)} vendas, {len(errors)} erros")
            
            return {
                'success': True,
                'processed_sales': processed_sales,
                'total_processed': len(processed_sales),
                'errors': errors,
                'total_errors': len(errors)
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar dados semanais: {e}")
            return {
                'success': False,
                'error': f'Erro ao processar planilha semanal: {str(e)}',
                'processed_sales': [],
                'errors': []
            }

    def process_sales_data_by_cells(self, df: pd.DataFrame, cell_mapping: Dict[str, str], start_row: int = 0, end_row: int = None) -> Dict[str, Any]:
        """
        Processa dados usando mapeamento de células específicas
        
        Args:
            df: DataFrame da planilha
            cell_mapping: Mapeamento de células (ex: {'vendedor': 'D', 'moeda': 'B', 'valor': 'E'})
            start_row: Linha inicial dos dados (0-indexed)
            end_row: Linha final dos dados (None = até o fim)
        """
        try:
            processed_sales = []
            errors = []
            vendedor_cache = {}
            
            # Determinar range de linhas
            if end_row is None:
                end_row = len(df)
            
            for row_idx in range(start_row, min(end_row, len(df))):
                try:
                    sale_data = {}
                    
                    # Extrair dados usando mapeamento de células
                    for field, col_letter in cell_mapping.items():
                        # Converter letra da coluna para índice (A=0, B=1, etc.)
                        col_idx = self._column_letter_to_index(col_letter)
                        
                        if col_idx < len(df.columns):
                            cell_value = df.iloc[row_idx, col_idx]
                            sale_data[field] = cell_value
                        else:
                            sale_data[field] = None
                    
                    # Validar se linha tem dados suficientes
                    if not self._is_valid_data_row(sale_data):
                        continue
                    
                    # Processar vendedor
                    vendedor_nome = str(sale_data.get('vendedor', '')).strip()
                    if not vendedor_nome:
                        errors.append(f"Linha {row_idx + 2}: Vendedor vazio")
                        continue
                        
                    if vendedor_nome not in vendedor_cache:
                        vendedor = self.db.query(Vendedor).filter(
                            Vendedor.nome.ilike(f'%{vendedor_nome}%'),
                            Vendedor.ativo == True
                        ).first()
                        vendedor_cache[vendedor_nome] = vendedor
                    else:
                        vendedor = vendedor_cache[vendedor_nome]
                    
                    if not vendedor:
                        errors.append(f"Linha {row_idx + 2}: Vendedor '{vendedor_nome}' não encontrado")
                        continue
                    
                    # Processar outros campos
                    processed_sale = self._process_sale_fields(sale_data, vendedor, row_idx + 2)
                    if processed_sale:
                        processed_sales.append(processed_sale)
                    else:
                        errors.append(f"Linha {row_idx + 2}: Erro no processamento dos dados")
                        
                except Exception as e:
                    errors.append(f"Linha {row_idx + 2}: Erro no processamento - {str(e)}")
            
            return {
                'success': True,
                'processed_sales': processed_sales,
                'total_processed': len(processed_sales),
                'errors': errors,
                'total_errors': len(errors)
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar dados por células: {e}")
            return {
                'success': False,
                'error': f'Erro ao processar planilha: {str(e)}',
                'processed_sales': [],
                'errors': []
            }

    def process_sales_data(self, df: pd.DataFrame, cell_mapping: Dict[str, str] = None, start_row: int = 0, end_row: int = None) -> Dict[str, Any]:
        """
        Processa os dados da planilha e converte para formato de vendas
        
        Args:
            df: DataFrame da planilha
            cell_mapping: Mapeamento de células específicas (opcional)
            start_row: Linha inicial dos dados (0-indexed) 
            end_row: Linha final dos dados (None = até o fim)
        
        Returns:
            Dict com vendas processadas e estatísticas
        """
        if cell_mapping:
            # Usar método de mapeamento por células
            return self.process_sales_data_by_cells(df, cell_mapping, start_row, end_row)
            
        # Método tradicional por colunas
        try:
            processed_sales = []
            errors = []
            vendedor_cache = {}  # Cache para vendedores
            
            for index, row in df.iterrows():
                try:
                    # Buscar vendedor (com cache)
                    vendedor_nome = str(row['vendedor']).strip()
                    if vendedor_nome not in vendedor_cache:
                        vendedor = self.db.query(Vendedor).filter(
                            Vendedor.nome.ilike(f'%{vendedor_nome}%'),
                            Vendedor.ativo == True
                        ).first()
                        vendedor_cache[vendedor_nome] = vendedor
                    else:
                        vendedor = vendedor_cache[vendedor_nome]
                    
                    if not vendedor:
                        errors.append(f"Linha {index + 2}: Vendedor '{vendedor_nome}' não encontrado")
                        continue
                    
                    # Processar data
                    data_venda = self._parse_date(row['data_venda'])
                    if not data_venda:
                        errors.append(f"Linha {index + 2}: Data inválida '{row['data_venda']}'")
                        continue
                    
                    # Processar valor
                    valor_bruto = self._parse_decimal(row['valor_bruto'])
                    if valor_bruto is None or valor_bruto <= 0:
                        errors.append(f"Linha {index + 2}: Valor inválido '{row['valor_bruto']}'")
                        continue
                    
                    # Processar moeda
                    moeda = self._parse_moeda(str(row['moeda']).strip().upper())
                    if not moeda:
                        errors.append(f"Linha {index + 2}: Moeda inválida '{row['moeda']}'")
                        continue
                    
                    # Processar método de pagamento
                    metodo_pagamento = self._parse_pagamento_metodo(str(row['metodo_pagamento']).strip().upper())
                    if not metodo_pagamento:
                        errors.append(f"Linha {index + 2}: Método de pagamento inválido '{row['metodo_pagamento']}'")
                        continue
                    
                    # Montar dados da venda
                    sale_data = {
                        'vendedor_id': vendedor.id,
                        'vendedor_nome': vendedor.nome,
                        'data_venda': data_venda,
                        'valor_bruto': valor_bruto,
                        'moeda': moeda,
                        'metodo_pagamento': metodo_pagamento,
                        'descricao_produto': str(row.get('descricao_produto', '')).strip() or None,
                        'observacoes': str(row.get('observacoes', '')).strip() or None,
                        'row_number': index + 2
                    }
                    
                    processed_sales.append(sale_data)
                    
                except Exception as e:
                    errors.append(f"Linha {index + 2}: Erro no processamento - {str(e)}")
            
            return {
                'success': True,
                'processed_sales': processed_sales,
                'total_processed': len(processed_sales),
                'errors': errors,
                'total_errors': len(errors)
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar dados da planilha: {e}")
            return {
                'success': False,
                'error': f'Erro ao processar planilha: {str(e)}',
                'processed_sales': [],
                'errors': []
            }
    
    def import_sales_to_database(self, processed_sales: List[Dict], created_by_user_id: str) -> Dict[str, Any]:
        """
        Importa as vendas processadas para o banco de dados
        
        Returns:
            Dict com estatísticas da importação
        """
        try:
            imported_count = 0
            skipped_count = 0
            errors = []
            
            for sale_data in processed_sales:
                try:
                    # Verificar se já existe uma venda igual (evitar duplicatas)
                    existing_sale = self.db.query(Venda).filter(
                        Venda.vendedor_id == sale_data['vendedor_id'],
                        Venda.data_venda == sale_data['data_venda'],
                        Venda.valor_bruto == sale_data['valor_bruto'],
                        Venda.moeda == sale_data['moeda']
                    ).first()
                    
                    if existing_sale:
                        skipped_count += 1
                        continue
                    
                    # Calcular valor líquido (implementar lógica de taxas se necessário)
                    valor_liquido = sale_data['valor_bruto']  # Por enquanto, sem taxas
                    
                    # Criar nova venda
                    nova_venda = Venda(
                        vendedor_id=sale_data['vendedor_id'],
                        data_venda=sale_data['data_venda'],
                        valor_bruto=sale_data['valor_bruto'],
                        valor_liquido=valor_liquido,
                        moeda=sale_data['moeda'],
                        metodo_pagamento=sale_data['metodo_pagamento'],
                        descricao_produto=sale_data['descricao_produto'],
                        observacoes=sale_data['observacoes'],
                        created_by=created_by_user_id
                    )
                    
                    self.db.add(nova_venda)
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Linha {sale_data['row_number']}: Erro na importação - {str(e)}")
            
            # Commit todas as vendas
            self.db.commit()
            
            return {
                'success': True,
                'imported_count': imported_count,
                'skipped_count': skipped_count,
                'errors': errors,
                'total_errors': len(errors)
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erro ao importar vendas: {e}")
            return {
                'success': False,
                'error': f'Erro ao importar vendas: {str(e)}',
                'imported_count': 0,
                'skipped_count': 0,
                'errors': []
            }
    
    def _parse_date(self, date_value) -> Optional[date]:
        """Converte valor para data"""
        if pd.isna(date_value):
            return None
        
        if isinstance(date_value, datetime):
            return date_value.date()
        
        if isinstance(date_value, date):
            return date_value
        
        # Tentar converter string
        try:
            if isinstance(date_value, str):
                # Formato DD/MM/YYYY
                if '/' in date_value:
                    return datetime.strptime(date_value.strip(), '%d/%m/%Y').date()
                # Formato YYYY-MM-DD
                elif '-' in date_value:
                    return datetime.strptime(date_value.strip(), '%Y-%m-%d').date()
        except:
            pass
        
        return None
    
    def _parse_decimal(self, value) -> Optional[Decimal]:
        """Converte valor para Decimal"""
        if pd.isna(value):
            return None
        
        try:
            # Limpar string (remover espaços, vírgulas como separador decimal)
            if isinstance(value, str):
                value = value.strip().replace(',', '.')
            
            return Decimal(str(value))
        except:
            return None
    
    def _parse_moeda(self, moeda_str: str) -> Optional[MoedaTipo]:
        """Converte string para MoedaTipo"""
        moeda_map = {
            'G$': MoedaTipo.G_DOLLAR,
            'R$': MoedaTipo.R_DOLLAR,  
            'U$': MoedaTipo.U_DOLLAR,
            'EUR': MoedaTipo.EUR
        }
        return moeda_map.get(moeda_str)
    
    def _parse_pagamento_metodo(self, metodo_str: str) -> Optional[PagamentoMetodo]:
        """Converte string para PagamentoMetodo"""
        metodo_map = {
            'PIX_POWER': PagamentoMetodo.PIX_POWER,
            'PIX_THAIS': PagamentoMetodo.PIX_THAIS,
            'PIX_MERCADO_PAGO': PagamentoMetodo.PIX_MERCADO_PAGO,
            'CREDITO': PagamentoMetodo.CREDITO,
            'DEBITO': PagamentoMetodo.DEBITO,
            'PY_TRANSFER_SUDAMERIS': PagamentoMetodo.PY_TRANSFER_SUDAMERIS,
            'PY_TRANSFER_INTERFISA': PagamentoMetodo.PY_TRANSFER_INTERFISA
        }
        return metodo_map.get(metodo_str)
    
    def _column_letter_to_index(self, col_letter: str) -> int:
        """Converte letra da coluna (A, B, C...) para índice (0, 1, 2...)"""
        col_letter = col_letter.upper().strip()
        result = 0
        for char in col_letter:
            result = result * 26 + (ord(char) - ord('A') + 1)
        return result - 1
    
    def _is_valid_data_row(self, sale_data: Dict) -> bool:
        """Verifica se a linha tem dados suficientes para ser processada"""
        # Verificar se pelo menos vendedor e valor existem
        vendedor = str(sale_data.get('vendedor', '')).strip()
        valor = sale_data.get('valor_bruto') or sale_data.get('valor')
        
        return bool(vendedor and valor and not pd.isna(valor))
    
    def _process_sale_fields(self, sale_data: Dict, vendedor, row_number: int) -> Optional[Dict]:
        """Processa e valida os campos de uma venda"""
        try:
            logger.info(f"Processando linha {row_number} - dados brutos: {sale_data}")
            
            # Processar data
            data_raw = sale_data.get('data_venda') or sale_data.get('data')
            logger.info(f"Linha {row_number} - data bruta: {data_raw} (tipo: {type(data_raw)})")
            
            data_venda = self._parse_date(data_raw)
            if not data_venda:
                logger.error(f"Linha {row_number} - falha no parsing da data: {data_raw}")
                return None
            
            # Processar valor
            valor_raw = sale_data.get('valor_bruto') or sale_data.get('valor')
            logger.info(f"Linha {row_number} - valor bruto: {valor_raw} (tipo: {type(valor_raw)})")
            
            valor_bruto = self._parse_decimal(valor_raw)
            if valor_bruto is None or valor_bruto <= 0:
                logger.error(f"Linha {row_number} - falha no parsing do valor: {valor_raw}")
                return None
            
            # Processar moeda
            moeda_raw = sale_data.get('moeda', 'R$')
            moeda_str = str(moeda_raw).strip().upper()
            logger.info(f"Linha {row_number} - moeda: {moeda_raw} -> {moeda_str}")
            
            moeda = self._parse_moeda(moeda_str)
            if not moeda:
                logger.warning(f"Linha {row_number} - moeda não reconhecida: {moeda_str}, usando R$ como padrão")
                moeda = MoedaTipo.R_DOLLAR  # Default para R$
            
            # Processar método de pagamento
            metodo_raw = sale_data.get('metodo_pagamento', 'PIX_POWER')
            metodo_str = str(metodo_raw).strip().upper()
            logger.info(f"Linha {row_number} - método pagamento: {metodo_raw} -> {metodo_str}")
            
            metodo_pagamento = self._parse_pagamento_metodo(metodo_str)
            if not metodo_pagamento:
                logger.warning(f"Linha {row_number} - método não reconhecido: {metodo_str}, usando PIX_POWER como padrão")
                metodo_pagamento = PagamentoMetodo.PIX_POWER  # Default
            
            result = {
                'vendedor_id': vendedor.id,
                'vendedor_nome': vendedor.nome,
                'data_venda': data_venda,
                'valor_bruto': valor_bruto,
                'moeda': moeda,
                'metodo_pagamento': metodo_pagamento,
                'descricao_produto': str(sale_data.get('descricao_produto', '')).strip() or None,
                'observacoes': str(sale_data.get('observacoes', '')).strip() or None,
                'row_number': row_number
            }
            
            logger.info(f"Linha {row_number} - processamento OK: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Erro ao processar campos da linha {row_number}: {e}")
            logger.error(f"Dados da linha {row_number}: {sale_data}")
            return None