"""
Endpoints para importação de vendas via Excel
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel
import tempfile
import os

from ...database import get_db
from ...dependencies import get_current_active_user, require_role
from ...models.usuario import Usuario
from ...services.excel_import_service import ExcelImportService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class OneDriveImportRequest(BaseModel):
    file_path: str
    access_token: str
    cell_mapping: Optional[Dict[str, str]] = None
    start_row: Optional[int] = 0
    end_row: Optional[int] = None
    
class ImportPreviewResponse(BaseModel):
    success: bool
    total_rows: int
    valid_rows: int
    errors: list
    preview_data: list
    
class ImportResultResponse(BaseModel):
    success: bool
    imported_count: int
    skipped_count: int
    total_errors: int
    errors: list

@router.post("/preview-onedrive", response_model=ImportPreviewResponse)
def preview_onedrive_import(
    request: OneDriveImportRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """
    Faz preview da importação de vendas do OneDrive
    """
    try:
        # Inicializar serviço
        import_service = ExcelImportService(db)
        
        # Autenticar OneDrive
        if not import_service.authenticate_onedrive(request.access_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token OneDrive inválido"
            )
        
        # Baixar e processar planilha
        df = import_service.download_excel_from_onedrive(request.file_path)
        if df is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arquivo não encontrado no OneDrive"
            )
        
        # Validar estrutura
        validation_result = import_service.validate_excel_structure(df, request.cell_mapping)
        if not validation_result['valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result['error']
            )
        
        # Processar dados
        process_result = import_service.process_sales_data(
            df, 
            cell_mapping=request.cell_mapping,
            start_row=request.start_row or 0,
            end_row=request.end_row
        )
        if not process_result['success']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=process_result['error']
            )
        
        # Preparar preview (primeiras 10 linhas válidas)
        preview_data = []
        valid_sales = process_result['processed_sales'][:10]
        
        for sale in valid_sales:
            preview_data.append({
                'vendedor_nome': sale['vendedor_nome'],
                'data_venda': sale['data_venda'].strftime('%d/%m/%Y'),
                'valor_bruto': float(sale['valor_bruto']),
                'moeda': sale['moeda'].value,
                'metodo_pagamento': sale['metodo_pagamento'].value,
                'descricao_produto': sale['descricao_produto'] or '',
                'row_number': sale['row_number']
            })
        
        return ImportPreviewResponse(
            success=True,
            total_rows=validation_result['total_rows'],
            valid_rows=process_result['total_processed'],
            errors=process_result['errors'],
            preview_data=preview_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no preview da importação: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@router.post("/import-onedrive", response_model=ImportResultResponse)
def import_from_onedrive(
    request: OneDriveImportRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """
    Importa vendas do OneDrive para o banco de dados
    """
    try:
        # Inicializar serviço
        import_service = ExcelImportService(db)
        
        # Autenticar OneDrive
        if not import_service.authenticate_onedrive(request.access_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token OneDrive inválido"
            )
        
        # Baixar e processar planilha
        df = import_service.download_excel_from_onedrive(request.file_path)
        if df is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Arquivo não encontrado no OneDrive"
            )
        
        # Validar estrutura
        validation_result = import_service.validate_excel_structure(df, request.cell_mapping)
        if not validation_result['valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result['error']
            )
        
        # Processar dados
        process_result = import_service.process_sales_data(
            df, 
            cell_mapping=request.cell_mapping,
            start_row=request.start_row or 0,
            end_row=request.end_row
        )
        if not process_result['success']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=process_result['error']
            )
        
        # Importar para o banco
        import_result = import_service.import_sales_to_database(
            process_result['processed_sales'],
            str(current_user.id)
        )
        
        if not import_result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=import_result['error']
            )
        
        return ImportResultResponse(
            success=True,
            imported_count=import_result['imported_count'],
            skipped_count=import_result['skipped_count'],
            total_errors=import_result['total_errors'],
            errors=import_result['errors']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na importação: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@router.post("/preview-upload")
def preview_file_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """
    Faz preview da importação via upload de arquivo Excel
    """
    try:
        # Verificar se é arquivo Excel
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo deve ser Excel (.xlsx ou .xls)"
            )
        
        # Salvar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = file.file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Inicializar serviço
            import_service = ExcelImportService(db)
            
            # Ler arquivo local
            df = import_service.read_local_excel(tmp_file_path)
            if df is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Erro ao ler arquivo Excel"
                )
            
            # Validar colunas
            validation_result = import_service.validate_excel_columns(df)
            if not validation_result['valid']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation_result['error']
                )
            
            # Processar dados
            process_result = import_service.process_sales_data(df)
            if not process_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=process_result['error']
                )
            
            # Preparar preview (primeiras 10 linhas válidas)
            preview_data = []
            valid_sales = process_result['processed_sales'][:10]
            
            for sale in valid_sales:
                preview_data.append({
                    'vendedor_nome': sale['vendedor_nome'],
                    'data_venda': sale['data_venda'].strftime('%d/%m/%Y'),
                    'valor_bruto': float(sale['valor_bruto']),
                    'moeda': sale['moeda'].value,
                    'metodo_pagamento': sale['metodo_pagamento'].value,
                    'descricao_produto': sale['descricao_produto'] or '',
                    'row_number': sale['row_number']
                })
            
            return {
                'success': True,
                'total_rows': validation_result['total_rows'],
                'valid_rows': process_result['total_processed'],
                'errors': process_result['errors'],
                'preview_data': preview_data
            }
            
        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no preview do upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@router.post("/import-upload")
def import_file_upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """
    Importa vendas via upload de arquivo Excel
    """
    try:
        # Verificar se é arquivo Excel
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo deve ser Excel (.xlsx ou .xls)"
            )
        
        # Salvar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = file.file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Inicializar serviço
            import_service = ExcelImportService(db)
            
            # Ler arquivo local
            df = import_service.read_local_excel(tmp_file_path)
            if df is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Erro ao ler arquivo Excel"
                )
            
            # Validar colunas
            validation_result = import_service.validate_excel_columns(df)
            if not validation_result['valid']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=validation_result['error']
                )
            
            # Processar dados
            process_result = import_service.process_sales_data(df)
            if not process_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=process_result['error']
                )
            
            # Importar para o banco
            import_result = import_service.import_sales_to_database(
                process_result['processed_sales'],
                str(current_user.id)
            )
            
            if not import_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=import_result['error']
                )
            
            return {
                'success': True,
                'imported_count': import_result['imported_count'],
                'skipped_count': import_result['skipped_count'],
                'total_errors': import_result['total_errors'],
                'errors': import_result['errors']
            }
            
        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na importação do upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@router.post("/preview-custom-format")
def preview_custom_format(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """
    Faz preview dos dados semanais da planilha VENDASgeral.xlsx
    
    Mapeamento da planilha:
    - D2=Junior, E2=Denis, F2=Sol, G2=Wiss, H2=Lucas (vendedores)
    - C3=G$, C4=EUR, C5=R$, C6=U$ (moedas)
    - Dados nas interseções (ex: D3 = vendas do Junior em G$)
    """
    try:
        # Verificar se é arquivo Excel
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo deve ser Excel (.xlsx ou .xls)"
            )
        
        # Salvar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = file.file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Inicializar serviço
            import_service = ExcelImportService(db)
            
            # Ler arquivo local
            df = import_service.read_local_excel(tmp_file_path)
            if df is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Erro ao ler arquivo Excel"
                )
            
            # Processar dados semanais usando o novo mapeamento
            process_result = import_service.process_weekly_sales_data(df)
            
            if not process_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=process_result['error']
                )
            
            # Preparar preview (todas as vendas válidas)
            preview_data = []
            valid_sales = process_result['processed_sales']
            
            for sale in valid_sales:
                preview_data.append({
                    'vendedor_nome': sale['vendedor_nome'],
                    'data_venda': sale['data_venda'].strftime('%d/%m/%Y'),
                    'valor_bruto': float(sale['valor_bruto']),
                    'moeda': sale['moeda'].value,
                    'metodo_pagamento': sale['metodo_pagamento'].value,
                    'descricao_produto': sale['descricao_produto'] or '',
                    'row_number': sale.get('cell_reference', sale['row_number'])
                })
            
            return {
                'success': True,
                'total_rows': len(df),
                'valid_rows': process_result['total_processed'],
                'errors': process_result['errors'],
                'preview_data': preview_data,
                'mapping_info': {
                    'type': 'weekly_summary',
                    'vendedores': ['Junior', 'Denis', 'Sol', 'Wiss', 'Lucas'],
                    'moedas': ['G$', 'EUR', 'R$', 'U$'],
                    'description': 'Dados semanais extraídos das interseções vendedor x moeda'
                }
            }
            
        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro no preview dos dados semanais: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@router.post("/import-custom-format")
def import_custom_format(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(["ADMIN", "GERENTE"]))
):
    """
    Importa dados semanais da planilha VENDASgeral.xlsx
    
    Processa os totais semanais por vendedor e moeda e cria registros de vendas
    """
    try:
        # Verificar se é arquivo Excel
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Arquivo deve ser Excel (.xlsx ou .xls)"
            )
        
        # Salvar arquivo temporário
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            content = file.file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Inicializar serviço
            import_service = ExcelImportService(db)
            
            # Ler arquivo local
            df = import_service.read_local_excel(tmp_file_path)
            if df is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Erro ao ler arquivo Excel"
                )
            
            # Processar dados semanais
            process_result = import_service.process_weekly_sales_data(df)
            
            if not process_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=process_result['error']
                )
            
            # Importar para o banco
            import_result = import_service.import_sales_to_database(
                process_result['processed_sales'],
                str(current_user.id)
            )
            
            if not import_result['success']:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=import_result['error']
                )
            
            return {
                'success': True,
                'imported_count': import_result['imported_count'],
                'skipped_count': import_result['skipped_count'],
                'total_errors': import_result['total_errors'],
                'errors': import_result['errors'],
                'mapping_info': {
                    'type': 'weekly_summary',
                    'description': 'Importação de totais semanais por vendedor e moeda'
                }
            }
            
        finally:
            # Limpar arquivo temporário
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro na importação dos dados semanais: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno: {str(e)}"
        )

@router.get("/template")
def download_template():
    """
    Retorna informações sobre o template da planilha Excel
    """
    return {
        'template_info': {
            'standard_format': {
                'required_columns': [
                    {'name': 'vendedor', 'description': 'Nome do vendedor', 'example': 'João Silva'},
                    {'name': 'data_venda', 'description': 'Data da venda (DD/MM/YYYY)', 'example': '15/01/2025'},
                    {'name': 'valor_bruto', 'description': 'Valor bruto da venda', 'example': '150.50'},
                    {'name': 'moeda', 'description': 'Moeda (G$, R$, U$, EUR)', 'example': 'R$'},
                    {'name': 'metodo_pagamento', 'description': 'Método de pagamento', 'example': 'PIX_POWER'}
                ]
            },
            'custom_format': {
                'description': 'Formato personalizado baseado na planilha VENDASgeral.xlsx',
                'cell_mapping': {
                    'A': 'data da venda',
                    'B': 'moeda utilizada', 
                    'C': 'método de pagamento',
                    'D': 'nome do vendedor',
                    'E': 'valor da venda'
                },
                'start_row': 11,
                'note': 'Use o endpoint /preview-custom-format ou /import-custom-format para este formato'
            },
            'payment_methods': [
                'PIX_POWER', 'PIX_THAIS', 'PIX_MERCADO_PAGO', 
                'CREDITO', 'DEBITO', 'PY_TRANSFER_SUDAMERIS', 'PY_TRANSFER_INTERFISA'
            ],
            'currencies': ['G$', 'R$', 'U$', 'EUR']
        }
    }