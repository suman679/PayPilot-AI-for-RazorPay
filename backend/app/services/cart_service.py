from sqlalchemy.orm import Session

from app.models import ActorType, Cart, CartItem, Product
from app.schemas import CartItemOut, CartOut


def get_or_create_cart(db: Session, user_id: str, session_id: str) -> Cart:
    cart = db.query(Cart).filter(Cart.session_id == session_id).first()
    if cart:
        return cart
    cart = Cart(user_id=user_id, session_id=session_id)
    db.add(cart)
    db.commit()
    db.refresh(cart)
    return cart


def add_item(
    db: Session, cart: Cart, product: Product, quantity: int = 1,
    added_by: ActorType = ActorType.AGENT, is_upsell: bool = False,
) -> CartItem:
    existing = next((i for i in cart.items if i.product_id == product.id), None)
    if existing:
        existing.quantity += quantity
        db.commit()
        db.refresh(existing)
        return existing
    item = CartItem(
        cart_id=cart.id, product_id=product.id, quantity=quantity,
        added_by=added_by, is_upsell=is_upsell,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def remove_item(db: Session, cart: Cart, item_id: str) -> bool:
    item = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        return False
    db.delete(item)
    db.commit()
    return True


def calculate_totals(cart: Cart) -> dict:
    subtotal = 0
    upsell_amount = 0
    for item in cart.items:
        line_total = item.product.price * item.quantity
        subtotal += line_total
        if item.is_upsell:
            upsell_amount += line_total
    return {"subtotal": subtotal, "upsell_amount": upsell_amount, "total": subtotal}


def to_cart_out(cart: Cart) -> CartOut:
    totals = calculate_totals(cart)
    items = [
        CartItemOut(
            id=i.id,
            product=i.product,
            quantity=i.quantity,
            is_upsell=i.is_upsell,
            line_total=i.product.price * i.quantity,
        )
        for i in cart.items
    ]
    return CartOut(id=cart.id, items=items, **totals)
