from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActorType, Order, Payment
from app.schemas import (
    CreatePaymentRequest, RazorpayOrderOut, RetryPaymentRequest,
    VerifyPaymentRequest, VerifyPaymentResponse,
)
from app.services import payment_service
from app.config import settings

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/create", response_model=RazorpayOrderOut)
def create_payment(req: CreatePaymentRequest, db: Session = Depends(get_db)):
    order = db.get(Order, req.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    try:
        payment = payment_service.create_payment_for_order(db, order, actor=ActorType.USER)
    except payment_service.PolicyBlockedError as e:
        raise HTTPException(403, detail=e.decision.as_dict())

    return RazorpayOrderOut(
        razorpay_order_id=payment.razorpay_order_id,
        razorpay_key_id=settings.RAZORPAY_KEY_ID or "rzp_test_mock_key",
        amount_paise=payment.amount * 100,
        currency=payment.currency,
        order_id=order.id,
        prefill_name=order.user.name,
        prefill_email=order.user.email,
    )


@router.post("/verify", response_model=VerifyPaymentResponse)
def verify_payment(req: VerifyPaymentRequest, db: Session = Depends(get_db)):
    order = db.get(Order, req.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment:
        raise HTTPException(400, "No payment record for this order")

    success, message, retries_remaining = payment_service.verify_and_record_payment(
        db, order, payment,
        razorpay_order_id=req.razorpay_order_id,
        razorpay_payment_id=req.razorpay_payment_id,
        razorpay_signature=req.razorpay_signature,
    )
    return VerifyPaymentResponse(
        success=success, order_status=order.status.value, message=message,
        retries_remaining=retries_remaining,
    )


@router.post("/retry", response_model=RazorpayOrderOut)
def retry_payment(req: RetryPaymentRequest, db: Session = Depends(get_db)):
    """Bounded retry: reuses the SAME Razorpay order (no duplicate order
    creation), gated by MAX_PAYMENT_RETRY_ATTEMPTS."""
    order = db.get(Order, req.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment:
        raise HTTPException(400, "No payment record for this order")

    from app import policy
    decision = policy.check_retry_allowed(db, payment)
    if not decision.allowed:
        raise HTTPException(403, detail=decision.as_dict())

    return RazorpayOrderOut(
        razorpay_order_id=payment.razorpay_order_id,
        razorpay_key_id=settings.RAZORPAY_KEY_ID or "rzp_test_mock_key",
        amount_paise=payment.amount * 100,
        currency=payment.currency,
        order_id=order.id,
        prefill_name=order.user.name,
        prefill_email=order.user.email,
    )


@router.get("/status/{order_id}")
def payment_status(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return payment_service.get_payment_status(db, order)


@router.post("/mock-complete", response_model=VerifyPaymentResponse)
def mock_complete(req: VerifyPaymentRequest, db: Session = Depends(get_db)):
    """DEMO-ONLY endpoint, active only when Razorpay is not configured (mock
    mode). Lets the customer UI simulate a checkout outcome without a real
    Razorpay account, while still exercising the SAME verify_and_record_payment
    code path (signature check, idempotency, retry limits, audit trail).
    Never available when real Razorpay test-mode keys are configured."""
    if not payment_service.gateway.is_mock:
        raise HTTPException(403, "mock-complete is disabled: Razorpay is configured for real test-mode checkout.")

    order = db.get(Order, req.order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if not payment:
        raise HTTPException(400, "No payment record for this order")

    outcome_signature = req.razorpay_signature  # "SIMULATE_SUCCESS" or "SIMULATE_FAILURE" from the UI
    if outcome_signature == "SIMULATE_SUCCESS":
        real_signature = payment_service.gateway._mock_signature(payment.razorpay_order_id, req.razorpay_payment_id)
    else:
        real_signature = "deliberately_invalid_signature"

    success, message, retries_remaining = payment_service.verify_and_record_payment(
        db, order, payment,
        razorpay_order_id=payment.razorpay_order_id,
        razorpay_payment_id=req.razorpay_payment_id,
        razorpay_signature=real_signature,
    )
    return VerifyPaymentResponse(success=success, order_status=order.status.value,
                                  message=message, retries_remaining=retries_remaining)
