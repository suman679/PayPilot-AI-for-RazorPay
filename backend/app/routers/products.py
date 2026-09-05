from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ProductOut
from app.services import product_service

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    q: str | None = None, category: str | None = None, color: str | None = None,
    max_price: int | None = None, min_price: int | None = None,
    db: Session = Depends(get_db),
):
    return product_service.search_products(
        db, query=q, category=category, color=color, max_price=max_price, min_price=min_price, limit=50,
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = product_service.get_product(db, product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return product
