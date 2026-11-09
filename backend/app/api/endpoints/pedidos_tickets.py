"""Read-only PDF and explicitly confirmed bag-ticket delivery."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from ...database import get_db
from ...dependencies import get_current_active_user
from ...schemas.pedido_reserva import ReservaCommand
from ...services import order_reservations, order_tickets, pdv_receipts

router = APIRouter()


@router.get('/{order_id}/reserva/ticket/status')
def ticket_status(order_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    order = order_reservations.authorized_order(db, order_id, user)
    return order_tickets.state(db, order)


@router.get('/{order_id}/reserva/ticket')
def ticket_pdf(order_id: uuid.UUID, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    order = order_reservations.authorized_order(db, order_id, user, lock=True)
    try:
        pdf = order_tickets.render(order_tickets.snapshot(db, order))
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    return Response(pdf, media_type='application/pdf', headers={'Cache-Control': 'no-store',
        'Content-Disposition': f'attachment; filename="Eleven-{"condicional" if order.delivered_at else "separado"}-{order.id.hex[:10]}.pdf"'})


@router.post('/{order_id}/reserva/ticket')
def print_ticket(order_id: uuid.UUID, body: ReservaCommand, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    order = order_reservations.authorized_order(db, order_id, user, lock=True)
    try:
        job = order_tickets.enqueue(db, order, body, user)
        result = {'job': pdv_receipts.receipt_state(job), 'printer': pdv_receipts.printer_info(pdv_receipts.destination(db))}
        db.commit()
        return result
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Identificador já utilizado. Confira o ticket anterior.') from None
