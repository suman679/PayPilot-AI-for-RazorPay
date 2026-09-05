from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order
from app.schemas import (
    CreateOrderRequest, OrderOut, ValidateCheckoutRequest,
)
from app.services import cart_service, order_service

router = APIRouter(prefix="/api", tags=["orders"])


@router.post("/checkout/validate")
def validate_checkout(req: ValidateCheckoutRequest, user_id: str, db: Session = Depends(get_db)):
    cart = cart_service.get_or_create_cart(db, user_id, req.session_id)
    if not cart.items:
        raise HTTPException(400, "Cart is empty")
    order = order_service.get_or_create_order_from_cart(db, cart, user_id, req.session_id)
    decision = order_service.validate_checkout(db, order)
    if req.user_confirmed and decision.allowed:
        order_service.confirm_order(db, order)
    return {"order_id": order.id, **decision.as_dict()}


@router.post("/orders", response_model=OrderOut)
def create_order(req: CreateOrderRequest, db: Session = Depends(get_db)):
    cart = cart_service.get_or_create_cart(db, req.user_id, req.session_id)
    if not cart.items:
        raise HTTPException(400, "Cart is empty")
    order = order_service.get_or_create_order_from_cart(db, cart, req.user_id, req.session_id)
    return order


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_order(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@router.get("/orders/{order_id}/detail")
def get_order_detail(order_id: str, db: Session = Depends(get_db)):
    """Full merchant-facing view: items, payments, audit trail (section 21)."""
    from app.audit import get_trail_for_order
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    trail = get_trail_for_order(db, order_id)
    return {
        "order": {
            "id": order.id, "status": order.status.value, "subtotal": order.subtotal,
            "upsell_amount": order.upsell_amount, "total_amount": order.total_amount,
            "user_confirmed": order.user_confirmed, "created_at": order.created_at.isoformat(),
        },
        "items": [
            {"product_id": i.product_id, "name": i.product_name, "unit_price": i.unit_price,
             "quantity": i.quantity, "is_upsell": i.is_upsell}
            for i in order.items
        ],
        "payments": [
            {"id": p.id, "razorpay_order_id": p.razorpay_order_id, "razorpay_payment_id": p.razorpay_payment_id,
             "amount": p.amount, "status": p.status.value,
             "attempts": [{"attempt_number": a.attempt_number, "result": a.result,
                           "failure_reason": a.failure_reason} for a in p.attempts]}
            for p in order.payments
        ],
        "audit_trail": [
            {"timestamp": e.timestamp.isoformat(), "event_type": e.event_type, "actor": e.actor.value,
             "amount": e.amount, "reason": e.reason, "result": e.result,
             "previous_state": e.previous_state, "new_state": e.new_state}
            for e in trail
        ],
    }
