from sqlalchemy.orm import Session
from sqlalchemy import func
from decimal import Decimal
from datetime import date, datetime
from typing import Optional, List
from ..models.venda import Venda, PagamentoMetodo
from ..models.money_transfer import MoneyTransfer, TransferStatus
from ..schemas.money_transfer import MoneyTransferCreate

class ThaisTransferService:
    """Service to handle automatic transfer accumulation for PIX_THAIS sales"""
    
    @staticmethod
    def is_thais_payment(metodo_pagamento: PagamentoMetodo) -> bool:
        """Check if payment method requires Thais transfer"""
        return metodo_pagamento == PagamentoMetodo.PIX_THAIS
    
    @staticmethod
    def get_or_create_pending_transfer(db: Session, transfer_date: date = None) -> MoneyTransfer:
        """Get existing pending transfer for today or create a new one"""
        if not transfer_date:
            transfer_date = date.today()
        
        # Look for existing pending transfer for the date
        existing_transfer = db.query(MoneyTransfer).filter(
            MoneyTransfer.transfer_date == transfer_date,
            MoneyTransfer.status == TransferStatus.PENDING,
            MoneyTransfer.currency == "R$"
        ).first()
        
        if existing_transfer:
            return existing_transfer
        
        # Create new pending transfer
        new_transfer = MoneyTransfer(
            transfer_date=transfer_date,
            amount_sent=Decimal('0.00'),
            thais_fee_percentage=Decimal('2.0'),
            thais_fee_amount=Decimal('0.00'),
            net_amount=Decimal('0.00'),
            currency="R$",
            status=TransferStatus.PENDING,
            transfer_method="Accumulated PIX_THAIS",
            notes=f"Auto-accumulated PIX_THAIS sales for {transfer_date}",
            created_by="System"
        )
        
        db.add(new_transfer)
        db.flush()  # Get the ID without committing
        return new_transfer
    
    @staticmethod
    def add_sale_to_pending_transfer(db: Session, venda: Venda) -> Optional[MoneyTransfer]:
        """Add a PIX_THAIS sale to the pending transfer accumulation"""
        if not ThaisTransferService.is_thais_payment(venda.metodo_pagamento):
            return None
        
        # Get or create pending transfer
        pending_transfer = ThaisTransferService.get_or_create_pending_transfer(
            db, venda.data_venda
        )
        
        # Add sale amount to pending transfer
        pending_transfer.amount_sent += venda.valor_liquido
        
        # Recalculate fees
        fee_amount = (pending_transfer.amount_sent * pending_transfer.thais_fee_percentage) / Decimal('100')
        pending_transfer.thais_fee_amount = fee_amount
        pending_transfer.net_amount = pending_transfer.amount_sent - fee_amount
        
        # Link sale to transfer
        venda.pending_transfer_id = pending_transfer.id
        venda.requires_thais_transfer = True
        
        # Update transfer notes
        sale_count = len(pending_transfer.related_sales) + 1
        pending_transfer.notes = f"Auto-accumulated PIX_THAIS sales for {pending_transfer.transfer_date} ({sale_count} sales)"
        
        return pending_transfer
    
    @staticmethod
    def get_pending_thais_balance(db: Session) -> dict:
        """Get current pending balance that needs to be sent to Thais"""
        # Get all pending transfers
        pending_transfers = db.query(MoneyTransfer).filter(
            MoneyTransfer.status == TransferStatus.PENDING
        ).all()
        
        total_pending = sum(t.amount_sent for t in pending_transfers)
        total_fees = sum(t.thais_fee_amount for t in pending_transfers)
        net_to_receive = sum(t.net_amount for t in pending_transfers)
        
        return {
            "total_pending_amount": total_pending,
            "total_thais_fees": total_fees,
            "net_amount_to_receive": net_to_receive,
            "transfer_count": len(pending_transfers),
            "transfers": pending_transfers
        }
    
    @staticmethod
    def process_transfer_to_thais(db: Session, transfer_id: str, 
                                 transfer_method: str = "PIX", 
                                 reference_number: str = None,
                                 sent_by: str = None) -> MoneyTransfer:
        """Process accumulated transfer - mark as sent to Thais"""
        transfer = db.query(MoneyTransfer).filter(MoneyTransfer.id == transfer_id).first()
        if not transfer:
            raise ValueError("Transfer not found")
        
        if transfer.status != TransferStatus.PENDING:
            raise ValueError("Transfer is not in pending status")
        
        # Update transfer details
        transfer.transfer_method = transfer_method
        transfer.reference_number = reference_number
        transfer.notes += f"\n\nSent to Thais on {datetime.now().strftime('%Y-%m-%d %H:%M')} by {sent_by or 'System'}"
        
        # Status remains PENDING until Thais delivers money to store
        return transfer
    
    @staticmethod
    def get_weekly_thais_summary(db: Session, start_date: date, end_date: date) -> dict:
        """Get summary of Thais-related amounts for weekly balance"""
        # PIX_THAIS sales in the period
        thais_sales = db.query(Venda).filter(
            Venda.metodo_pagamento == PagamentoMetodo.PIX_THAIS,
            Venda.data_venda >= start_date,
            Venda.data_venda <= end_date
        ).all()
        
        # Transfers delivered in the period
        delivered_transfers = db.query(MoneyTransfer).filter(
            MoneyTransfer.status == TransferStatus.DELIVERED,
            MoneyTransfer.delivery_confirmed_at >= datetime.combine(start_date, datetime.min.time()),
            MoneyTransfer.delivery_confirmed_at <= datetime.combine(end_date, datetime.max.time())
        ).all()
        
        # Pending transfers (money sent but not delivered)
        pending_transfers = db.query(MoneyTransfer).filter(
            MoneyTransfer.status == TransferStatus.PENDING,
            MoneyTransfer.transfer_date >= start_date,
            MoneyTransfer.transfer_date <= end_date
        ).all()
        
        thais_sales_total = sum(s.valor_liquido for s in thais_sales)
        delivered_amount = sum(t.net_amount for t in delivered_transfers)
        pending_amount = sum(t.net_amount for t in pending_transfers)
        fees_paid = sum(t.thais_fee_amount for t in delivered_transfers + pending_transfers)
        
        return {
            "thais_sales_total": thais_sales_total,
            "delivered_to_store": delivered_amount,
            "pending_with_thais": pending_amount,
            "total_fees_paid": fees_paid,
            "net_cash_impact": delivered_amount - pending_amount,  # Positive = money received, Negative = money sent
            "sales_count": len(thais_sales),
            "delivered_transfers_count": len(delivered_transfers),
            "pending_transfers_count": len(pending_transfers)
        }