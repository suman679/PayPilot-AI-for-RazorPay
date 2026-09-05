from datetime import datetime

from sqlalchemy.orm import Session

from app import policy
from app.audit import record_event
from app.config import settings
from app.models import ActorType, Order, OrderStatus, Payment, PaymentAttempt, PaymentStatus
from app.services.razorpay_client import SignatureVerificationError, gateway


class PolicyBlockedError(Exception):
    def __init__(self, decision: policy.PolicyDecision):
        self.decision = decision
        super().__init__(decision.reason)


def create_payment_for_order(db: Session, order: Order, actor: ActorType = ActorType.USER) -> Payment:
    """Creates (or reuses) the Razorpay order for a PayPilot order. Idempotent:
    a second call for the same order returns the existing Payment row instead
    of minting a new Razorpay order (section 7)."""

    # 1. Confirmation gate
    confirm_decision = policy.check_user_confirmation(order)
    if not confirm_decision.allowed:
        record_event(db, event_type="PAYMENT_BLOCKED", actor=actor, order_id=order.id,
                      amount=order.total_amount, reason=confirm_decision.reason, result="BLOCKED")
        raise PolicyBlockedError(confirm_decision)

    # 2. Transaction limit gate
    limit_decision = policy.check_transaction_limit(order.total_amount)
    if not limit_decision.allowed:
        record_event(db, event_type="PAYMENT_BLOCKED", actor=actor, order_id=order.id,
                      amount=order.total_amount, reason=limit_decision.reason, result="BLOCKED")
        raise PolicyBlockedError(limit_decision)

    # 3. Idempotency: reuse existing Razorpay order if present
    existing = db.query(Payment).filter(Payment.order_id == order.id).first()
    if existing:
        record_event(db, event_type="RAZORPAY_ORDER_REUSED", actor=ActorType.SYSTEM, order_id=order.id,
                      amount=order.total_amount,
                      reason="Existing Razorpay order found; reusing to avoid duplicate order creation.")
        return existing

    creation_decision = policy.check_order_creation_allowed(db, order)
    # (Already guaranteed allowed since `existing` is None, kept for defense in depth / audit clarity)

    rp_order = gateway.create_order(
        amount_paise=order.total_amount * 100,
        currency=order.currency,
        receipt=order.id,
        notes={"paypilot_order_id": order.id, "user_id": order.user_id},
    )

    payment = Payment(
        order_id=order.id,
        razorpay_order_id=rp_order["id"],
        amount=order.total_amount,
        currency=order.currency,
        status=PaymentStatus.CREATED,
    )
    db.add(payment)
    order.status = OrderStatus.PAYMENT_PENDING
    db.commit()
    db.refresh(payment)

    record_event(
        db, event_type="RAZORPAY_ORDER_CREATED", actor=ActorType.SYSTEM, order_id=order.id,
        amount=order.total_amount,
        reason=("[SIMULATED] " if gateway.is_mock else "") + f"Razorpay {'mock ' if gateway.is_mock else ''}order created.",
        previous_state=OrderStatus.PENDING_CONFIRMATION.value, new_state=OrderStatus.PAYMENT_PENDING.value,
        metadata={"razorpay_order_id": rp_order["id"], "is_mock": gateway.is_mock},
    )
    return payment


def verify_and_record_payment(
    db: Session, order: Order, payment: Payment, *,
    razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str,
) -> tuple[bool, str, int]:
    """Server-side signature verification - the ONLY source of truth for
    payment success. Returns (success, message, retries_remaining)."""

    retry_decision = policy.check_retry_allowed(db, payment)
    attempt_number = (
        db.query(PaymentAttempt).filter(PaymentAttempt.payment_id == payment.id).count() + 1
    )

    if razorpay_order_id != payment.razorpay_order_id:
        return _record_failure(db, order, payment, attempt_number,
                                "Razorpay order id mismatch - possible tampering.", retry_decision)

    try:
        gateway.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except SignatureVerificationError as e:
        return _record_failure(db, order, payment, attempt_number, f"Signature verification failed: {e}", retry_decision)

    # Success
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.status = PaymentStatus.VERIFIED
    payment.verified_at = datetime.utcnow()
    prev_status = order.status.value
    order.status = OrderStatus.PAID
    db.add(PaymentAttempt(
        payment_id=payment.id, attempt_number=attempt_number, result="SUCCESS",
        raw_payload={"razorpay_payment_id": razorpay_payment_id},
    ))
    db.commit()

    record_event(db, event_type="PAYMENT_VERIFIED", actor=ActorType.SYSTEM, order_id=order.id,
                 amount=order.total_amount, reason="Signature verified server-side; payment confirmed.",
                 previous_state=prev_status, new_state=OrderStatus.PAID.value,
                 metadata={"razorpay_payment_id": razorpay_payment_id, "is_mock": gateway.is_mock})
    record_event(db, event_type="ORDER_CONFIRMED", actor=ActorType.SYSTEM, order_id=order.id,
                 amount=order.total_amount, reason="Order confirmed after verified payment.",
                 previous_state=OrderStatus.PAID.value, new_state=OrderStatus.PAID.value)

    return True, "Payment verified successfully.", 0


def _record_failure(db: Session, order: Order, payment: Payment, attempt_number: int,
                     reason: str, retry_decision: policy.PolicyDecision) -> tuple[bool, str, int]:
    payment.status = PaymentStatus.FAILED
    db.add(PaymentAttempt(
        payment_id=payment.id, attempt_number=attempt_number, result="FAILED",
        failure_reason=reason,
    ))
    prev_status = order.status.value
    if not retry_decision.allowed:
        order.status = OrderStatus.FAILED
    db.commit()

    record_event(db, event_type="PAYMENT_ATTEMPT_FAILED", actor=ActorType.SYSTEM, order_id=order.id,
                 amount=order.total_amount, reason=reason, result="ERROR",
                 previous_state=prev_status, new_state=order.status.value,
                 metadata={"attempt_number": attempt_number})

    retries_remaining = max(settings.MAX_PAYMENT_RETRY_ATTEMPTS - attempt_number, 0)
    if not retry_decision.allowed:
        record_event(db, event_type="PAYMENT_RETRY_LIMIT_REACHED", actor=ActorType.SYSTEM, order_id=order.id,
                     amount=order.total_amount, reason="Maximum retry attempts reached.", result="BLOCKED")
        return False, ("Payment could not be completed after the allowed attempts. "
                        "Please try another payment method or contact support."), 0

    return False, "Payment wasn't completed. No successful payment was recorded.", retries_remaining


def get_payment_status(db: Session, order: Order) -> dict:
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment:
        return {"status": "NO_PAYMENT_ATTEMPTED", "order_status": order.status.value}
    return {
        "status": payment.status.value,
        "order_status": order.status.value,
        "razorpay_order_id": payment.razorpay_order_id,
        "attempts": len(payment.attempts),
    }
