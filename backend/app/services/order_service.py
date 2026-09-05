import hashlib
from datetime import datetime

from sqlalchemy.orm import Session

from app import policy
from app.audit import record_event
from app.models import ActorType, Cart, Order, OrderItem, OrderStatus
from app.services.cart_service import calculate_totals


def build_idempotency_key(cart: Cart) -> str:
    """Deterministic key derived from cart contents so re-submitting the same
    cart never mints a second order. (Section 7 - idempotency.)"""
    basis = "|".join(sorted(f"{i.product_id}:{i.quantity}:{i.is_upsell}" for i in cart.items))
    raw = f"{cart.id}:{basis}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_or_create_order_from_cart(db: Session, cart: Cart, user_id: str, session_id: str) -> Order:
    """Idempotent: if an order already exists for this exact cart state, reuse
    it rather than creating a duplicate."""
    idem_key = build_idempotency_key(cart)
    existing = db.query(Order).filter(Order.idempotency_key == idem_key).first()
    if existing and existing.status != OrderStatus.FAILED:
        return existing

    totals = calculate_totals(cart)
    order = Order(
        user_id=user_id,
        session_id=session_id,
        status=OrderStatus.PENDING_CONFIRMATION,
        subtotal=totals["subtotal"],
        upsell_amount=totals["upsell_amount"],
        total_amount=totals["total"],
        idempotency_key=idem_key,
    )
    db.add(order)
    db.flush()
    for i in cart.items:
        db.add(OrderItem(
            order_id=order.id, product_id=i.product_id, product_name=i.product.name,
            unit_price=i.product.price, quantity=i.quantity, is_upsell=i.is_upsell,
        ))
    db.commit()
    db.refresh(order)

    record_event(
        db, event_type="ORDER_CREATED", actor=ActorType.SYSTEM, order_id=order.id,
        user_id=user_id, session_id=session_id, amount=order.total_amount,
        reason="Order created from cart pending user confirmation.",
        previous_state=None, new_state=order.status.value,
    )
    return order


def validate_checkout(db: Session, order: Order) -> policy.PolicyDecision:
    """Runs every pre-payment policy check and returns the FIRST failing
    decision, or an overall-allowed decision with the combined explanation."""
    limit_decision = policy.check_transaction_limit(order.total_amount)
    if not limit_decision.allowed:
        record_event(
            db, event_type="CHECKOUT_BLOCKED", actor=ActorType.SYSTEM, order_id=order.id,
            amount=order.total_amount, reason=limit_decision.reason, result="BLOCKED",
        )
        return limit_decision
    return policy.PolicyDecision(
        allowed=True,
        reason="Checkout passes all policy checks.",
        explanation_bullets=[
            f"Total ₹{order.total_amount} is within policy limit.",
            "Awaiting explicit user confirmation before payment.",
        ],
    )


def confirm_order(db: Session, order: Order) -> Order:
    """Records the ONE moment of explicit user consent this whole system
    hinges on. Nothing downstream may charge money without this having
    happened first."""
    order.user_confirmed = True
    order.user_confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    record_event(
        db, event_type="CHECKOUT_CONFIRMATION", actor=ActorType.USER, order_id=order.id,
        amount=order.total_amount, reason="User explicitly confirmed checkout.",
        previous_state=OrderStatus.PENDING_CONFIRMATION.value, new_state=OrderStatus.PENDING_CONFIRMATION.value,
    )
    return order


def cancel_order(db: Session, order: Order, reason: str) -> Order:
    prev = order.status.value
    order.status = OrderStatus.CANCELLED
    db.commit()
    db.refresh(order)
    record_event(
        db, event_type="ORDER_CANCELLED", actor=ActorType.SYSTEM, order_id=order.id,
        reason=reason, previous_state=prev, new_state=order.status.value,
    )
    return order
