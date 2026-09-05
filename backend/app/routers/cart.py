from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActorType
from app.schemas import AddToCartRequest, CartOut
from app.services import cart_service, product_service

router = APIRouter(prefix="/api/cart", tags=["cart"])


@router.get("", response_model=CartOut)
def get_cart(session_id: str, user_id: str, db: Session = Depends(get_db)):
    cart = cart_service.get_or_create_cart(db, user_id, session_id)
    return cart_service.to_cart_out(cart)


@router.post("/items", response_model=CartOut)
def add_item(req: AddToCartRequest, user_id: str, db: Session = Depends(get_db)):
    product = product_service.get_product(db, req.product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    cart = cart_service.get_or_create_cart(db, user_id, req.session_id)
    cart_service.add_item(db, cart, product, quantity=req.quantity,
                           added_by=ActorType.USER, is_upsell=req.is_upsell)
    return cart_service.to_cart_out(cart)


@router.delete("/items/{item_id}", response_model=CartOut)
def remove_item(item_id: str, session_id: str, user_id: str, db: Session = Depends(get_db)):
    cart = cart_service.get_or_create_cart(db, user_id, session_id)
    cart_service.remove_item(db, cart, item_id)
    return cart_service.to_cart_out(cart)
