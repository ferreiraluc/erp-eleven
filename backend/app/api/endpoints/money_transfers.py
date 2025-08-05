from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from decimal import Decimal
from datetime import datetime
from ...database import get_db
from ...models.money_transfer import MoneyTransfer, TransferStatus
from ...schemas.money_transfer import (
    MoneyTransferCreate, 
    MoneyTransferResponse, 
    MoneyTransferUpdate,
    DeliveryConfirmation,
    TransferSummary
)

router = APIRouter()

@router.get("/", response_model=List[MoneyTransferResponse])
def list_transfers(
    status: TransferStatus = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """List money transfers, optionally filtered by status"""
    query = db.query(MoneyTransfer)
    
    if status:
        query = query.filter(MoneyTransfer.status == status)
    
    transfers = query.order_by(desc(MoneyTransfer.transfer_date)).offset(skip).limit(limit).all()
    return transfers

@router.get("/pending", response_model=List[MoneyTransferResponse])
def list_pending_transfers(db: Session = Depends(get_db)):
    """List all pending transfers (money sent but not yet delivered)"""
    return db.query(MoneyTransfer).filter(
        MoneyTransfer.status == TransferStatus.PENDING
    ).order_by(desc(MoneyTransfer.transfer_date)).all()

@router.get("/summary", response_model=TransferSummary)
def get_transfer_summary(db: Session = Depends(get_db)):
    """Get summary of transfers for dashboard"""
    
    # Count pending and delivered transfers
    pending_count = db.query(MoneyTransfer).filter(
        MoneyTransfer.status == TransferStatus.PENDING
    ).count()
    
    delivered_count = db.query(MoneyTransfer).filter(
        MoneyTransfer.status == TransferStatus.DELIVERED
    ).count()
    
    # Sum amounts
    pending_transfers = db.query(MoneyTransfer).filter(
        MoneyTransfer.status == TransferStatus.PENDING
    ).all()
    pending_amount = sum(t.net_amount for t in pending_transfers) if pending_transfers else Decimal('0')
    
    delivered_transfers = db.query(MoneyTransfer).filter(
        MoneyTransfer.status == TransferStatus.DELIVERED
    ).all()
    delivered_amount = sum(t.net_amount for t in delivered_transfers) if delivered_transfers else Decimal('0')
    
    # Total fees paid to Thais
    all_transfers = db.query(MoneyTransfer).all()
    total_fees = sum(t.thais_fee_amount for t in all_transfers) if all_transfers else Decimal('0')
    
    # Last transfer date
    last_transfer = db.query(MoneyTransfer).order_by(desc(MoneyTransfer.transfer_date)).first()
    last_date = last_transfer.transfer_date if last_transfer else None
    
    return TransferSummary(
        total_pending=pending_count,
        total_delivered=delivered_count,
        pending_amount=pending_amount,
        delivered_amount=delivered_amount,
        total_fees_paid=total_fees,
        last_transfer_date=last_date
    )

@router.post("/", response_model=MoneyTransferResponse)
def create_transfer(transfer: MoneyTransferCreate, db: Session = Depends(get_db)):
    """Create new money transfer to Thais"""
    
    # Calculate Thais' fee and net amount
    fee_percentage = transfer.thais_fee_percentage or Decimal("2.0")
    fee_amount = (transfer.amount_sent * fee_percentage) / Decimal("100")
    net_amount = transfer.amount_sent - fee_amount
    
    transfer_data = {
        **transfer.dict(),
        "thais_fee_amount": fee_amount,
        "net_amount": net_amount,
        "status": TransferStatus.PENDING
    }
    
    db_transfer = MoneyTransfer(**transfer_data)
    db.add(db_transfer)
    db.commit()
    db.refresh(db_transfer)
    return db_transfer

@router.get("/{transfer_id}", response_model=MoneyTransferResponse)
def get_transfer(transfer_id: str, db: Session = Depends(get_db)):
    """Get specific transfer by ID"""
    transfer = db.query(MoneyTransfer).filter(MoneyTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    return transfer

@router.put("/{transfer_id}", response_model=MoneyTransferResponse)
def update_transfer(
    transfer_id: str, 
    transfer_update: MoneyTransferUpdate, 
    db: Session = Depends(get_db)
):
    """Update transfer details"""
    transfer = db.query(MoneyTransfer).filter(MoneyTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    
    # If amount or fee percentage changes, recalculate
    update_data = transfer_update.dict(exclude_unset=True)
    
    if "amount_sent" in update_data or "thais_fee_percentage" in update_data:
        amount_sent = update_data.get("amount_sent", transfer.amount_sent)
        fee_percentage = update_data.get("thais_fee_percentage", transfer.thais_fee_percentage)
        
        fee_amount = (amount_sent * fee_percentage) / Decimal("100")
        net_amount = amount_sent - fee_amount
        
        update_data["thais_fee_amount"] = fee_amount
        update_data["net_amount"] = net_amount
    
    for field, value in update_data.items():
        setattr(transfer, field, value)
    
    db.commit()
    db.refresh(transfer)
    return transfer

@router.post("/{transfer_id}/confirm-delivery", response_model=MoneyTransferResponse)
def confirm_delivery(
    transfer_id: str, 
    confirmation: DeliveryConfirmation, 
    db: Session = Depends(get_db)
):
    """Confirm that money has been delivered to the store"""
    transfer = db.query(MoneyTransfer).filter(MoneyTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    
    if transfer.status == TransferStatus.DELIVERED:
        raise HTTPException(status_code=400, detail="Transfer already confirmed as delivered")
    
    # Update transfer status
    transfer.status = TransferStatus.DELIVERED
    transfer.delivery_confirmed_at = datetime.utcnow()
    transfer.delivery_confirmed_by = confirmation.confirmed_by
    
    if confirmation.notes:
        # Append to existing notes
        if transfer.notes:
            transfer.notes += f"\n\nDelivery confirmation: {confirmation.notes}"
        else:
            transfer.notes = f"Delivery confirmation: {confirmation.notes}"
    
    db.commit()
    db.refresh(transfer)
    return transfer

@router.post("/{transfer_id}/cancel", response_model=MoneyTransferResponse)
def cancel_transfer(transfer_id: str, reason: str = None, db: Session = Depends(get_db)):
    """Cancel a transfer"""
    transfer = db.query(MoneyTransfer).filter(MoneyTransfer.id == transfer_id).first()
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    
    if transfer.status == TransferStatus.DELIVERED:
        raise HTTPException(status_code=400, detail="Cannot cancel delivered transfer")
    
    transfer.status = TransferStatus.CANCELLED
    
    if reason:
        if transfer.notes:
            transfer.notes += f"\n\nCancellation reason: {reason}"
        else:
            transfer.notes = f"Cancellation reason: {reason}"
    
    db.commit()
    db.refresh(transfer)
    return transfer