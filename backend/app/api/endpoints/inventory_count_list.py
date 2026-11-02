"""Signed count-sheet previews and confirmed A4 document printing."""
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import require_role
from ...schemas.inventory_count_list import Selection, SignedList, PrintList
from ...services import inventory_count_list as lists

router = APIRouter()
operator = require_role(['ADMIN', 'GERENTE'])


def pdf_response(content):
    return Response(content, media_type='application/pdf', headers={
        'Cache-Control': 'no-store',
        'Content-Disposition': 'inline; filename="eleven-conferencia-estoque.pdf"',
    })


@router.post('/preview')
def preview(body: Selection, response: Response, db: Session = Depends(get_db), user=Depends(operator)):
    response.headers['Cache-Control'] = 'no-store'
    return lists.preview(db, user.id, body.item_ids)


@router.post('/pdf')
def pdf(body: SignedList, user=Depends(operator)):
    return pdf_response(lists.render(lists.verify(body, user.id)))


@router.post('/print')
def print_list(body: PrintList, response: Response, db: Session = Depends(get_db), user=Depends(operator)):
    response.headers['Cache-Control'] = 'no-store'
    return lists.enqueue(db, user, body)


@router.get('/jobs/{job_id}')
def job(job_id: UUID, response: Response, db: Session = Depends(get_db), user=Depends(operator)):
    response.headers['Cache-Control'] = 'no-store'
    return lists.job_view(db, lists.owned_job(db, user.id, job_id))


@router.get('/jobs/{job_id}/pdf')
def job_pdf(job_id: UUID, db: Session = Depends(get_db), user=Depends(operator)):
    job = lists.owned_job(db, user.id, job_id)
    return pdf_response(job.pdf or lists.render(job.snapshot))
