"""Explicit manager-only advice, review and confirmation; catalog reads stay local."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ...database import get_db
from ...dependencies import require_role
from ...models.usuario import Usuario
from ...schemas.inventory_grade_analysis import (
    GradeAnalysisRequest, GradeAnalysisResponse,
    GradeLinkPreviewRequest, GradeLinkPreviewResponse,
    GradeLinkCommitRequest, GradeLinkCommitResponse,
)
from ...services.inventory_grade_analysis import (
    analyze_grades, preview_grade_links, commit_grade_links,
)

router = APIRouter()
manager = require_role(['ADMIN', 'GERENTE'])


@router.post('/grades/ai-analysis', response_model=GradeAnalysisResponse)
def analyze(request: GradeAnalysisRequest, response: Response,
            db: Session = Depends(get_db), user: Usuario = Depends(manager)):
    response.headers['Cache-Control'] = 'no-store'
    return analyze_grades(db, request, user)


@router.post('/grades/preview', response_model=GradeLinkPreviewResponse)
def preview(request: GradeLinkPreviewRequest, response: Response,
            db: Session = Depends(get_db), user: Usuario = Depends(manager)):
    response.headers['Cache-Control'] = 'no-store'
    return preview_grade_links(db, request, user)


@router.post('/grades/commit', response_model=GradeLinkCommitResponse)
def commit(request: GradeLinkCommitRequest, response: Response,
           db: Session = Depends(get_db), user: Usuario = Depends(manager)):
    response.headers['Cache-Control'] = 'no-store'
    return commit_grade_links(db, request, user)
