from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...models.venda import Venda
from ...schemas.venda import VendaCreate, VendaResponse

router = APIRouter()

@router.get("/", response_model=List[VendaResponse])
def listar_vendas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    vendas = db.query(Venda).offset(skip).limit(limit).all()
    return vendas

@router.post("/", response_model=VendaResponse)
def criar_venda(venda: VendaCreate, db: Session = Depends(get_db)):
    db_venda = Venda(**venda.dict())
    db.add(db_venda)
    db.commit()
    db.refresh(db_venda)
    return db_venda

@router.get("/{venda_id}", response_model=VendaResponse)
def obter_venda(venda_id: str, db: Session = Depends(get_db)):
    venda = db.query(Venda).filter(Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    return venda