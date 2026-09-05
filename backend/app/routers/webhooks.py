from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import record_event
from app.database import get_db
from app.models import ActorType, Order, OrderStatus, Payment, PaymentStatus, WebhookEvent
from app.services.razorpay_client import gateway

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    body = await request.body()

    if not gateway.verify_webhook_signature(body, x_razorpay_signature or ""):
        record_event(db, event_type="WEBHOOK_SIGNATURE_INVALID", actor=ActorType.WEBHOOK,
                     reason="Rejected webhook with invalid signature.", result="BLOCKED")
        raise HTTPException(400, "Invalid webhook signature")

    payload = await request.json()
    event_id = payload.get("id") or payload.get("event_id")
    event_type = payload.get("event", "unknown")

    # ---- Deduplication: the same delivery is never processed twice ----
    if event_id:
        existing = db.query(WebhookEvent).filter(WebhookEvent.razorpay_event_id == event_id).first()
        if existing:
            return {"status": "duplicate_ignored"}

    db.add(WebhookEvent(razorpay_event_id=event_id, event_type=event_type, payload=payload))
    db.commit()

    entity = (payload.get("payload", {}).get("payment", {}).get("entity", {}))
    rp_order_id = entity.get("order_id")
    if rp_order_id:
        payment = db.query(Payment).filter(Payment.razorpay_order_id == rp_order_id).first()
        if payment:
            order = db.get(Order, payment.order_id)
            if event_type == "payment.captured" and order.status != OrderStatus.PAID:
                prev = order.status.value
                order.status = OrderStatus.PAID
                payment.status = PaymentStatus.VERIFIED
                db.commit()
                record_event(db, event_type="WEBHOOK_PAYMENT_CAPTURED", actor=ActorType.WEBHOOK,
                             order_id=order.id, amount=order.total_amount,
                             reason="Webhook confirmed payment capture.",
                             previous_state=prev, new_state=OrderStatus.PAID.value)
            elif event_type == "payment.failed":
                record_event(db, event_type="WEBHOOK_PAYMENT_FAILED", actor=ActorType.WEBHOOK,
                             order_id=order.id, reason="Webhook reported payment failure.", result="ERROR")

    record_event(db, event_type="WEBHOOK_RECEIVED", actor=ActorType.WEBHOOK,
                 reason=f"Processed webhook event {event_type}", metadata={"event_id": event_id})
    return {"status": "processed"}
