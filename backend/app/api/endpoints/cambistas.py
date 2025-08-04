from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...models.cambista import Cambista
from ...schemas.cambista import CambistaCreate, CambistaResponse

router = APIRouter()

@router.get("/", response_model=List[CambistaResponse])
def listar_cambistas(db: Session = Depends(get_db)):
    cambistas = db.query(Cambista).filter(Cambista.ativo == True).all()
    return cambistas

@router.post("/", response_model=CambistaResponse)
def criar_cambista(cambista: CambistaCreate, db: Session = Depends(get_db)):
    db_cambista = Cambista(**cambista.dict())
    db.add(db_cambista)
    db.commit()
    db.refresh(db_cambista)
    return db_cambista

@router.get("/{cambista_id}", response_model=CambistaResponse)
def obter_cambista(cambista_id: str, db: Session = Depends(get_db)):
    cambista = db.query(Cambista).filter(Cambista.id == cambista_id).first()
    if not cambista:
        raise HTTPException(status_code=404, detail="Cambista não encontrado")
    return cambista