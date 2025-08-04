from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...models.vendedor import Vendedor
from ...schemas.vendedor import VendedorCreate, VendedorResponse

router = APIRouter()

@router.get("/", response_model=List[VendedorResponse])
def listar_vendedores(db: Session = Depends(get_db)):
    vendedores = db.query(Vendedor).filter(Vendedor.ativo == True).all()
    return vendedores

@router.post("/", response_model=VendedorResponse)
def criar_vendedor(vendedor: VendedorCreate, db: Session = Depends(get_db)):
    db_vendedor = Vendedor(**vendedor.dict())
    db.add(db_vendedor)
    db.commit()
    db.refresh(db_vendedor)
    return db_vendedor

@router.get("/{vendedor_id}", response_model=VendedorResponse)
def obter_vendedor(vendedor_id: str, db: Session = Depends(get_db)):
    vendedor = db.query(Vendedor).filter(Vendedor.id == vendedor_id).first()
    if not vendedor:
        raise HTTPException(status_code=404, detail="Vendedor não encontrado")
    return vendedor