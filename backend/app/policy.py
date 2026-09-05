"""
Policy engine - the financial safety model.

The agent (LLM or rule-based) may PROPOSE an action ("charge the user
₹7,000"). This module is the only place that DECIDES whether the action is
allowed. It never trusts the caller's judgement; it re-derives the truth
(cart contents, prior attempts, confirmation flags) from the database on
every call.

Every decision returns a `PolicyDecision` with a human-readable explanation,
which callers must surface to the user and log to the audit trail.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Order, Payment, PaymentAttempt


@dataclass
class PolicyDecision:
    allowed: bool
    reason: str
    explanation_bullets: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "explanation": self.explanation_bullets,
        }


def check_transaction_limit(amount_inr: int) -> PolicyDecision:
    """Section 4/5: hard ceiling on any single transaction."""
    limit = settings.MAX_TRANSACTION_AMOUNT_INR
    if amount_inr > limit:
        return PolicyDecision(
            allowed=False,
            reason=f"Amount ₹{amount_inr} exceeds the ₹{limit} transaction policy limit.",
            explanation_bullets=[
                f"Requested amount ₹{amount_inr} exceeds ₹{limit} transaction policy.",
                "The agent cannot override this limit; a human must adjust policy configuration.",
            ],
        )
    return PolicyDecision(
        allowed=True,
        reason=f"Amount ₹{amount_inr} is within the ₹{limit} transaction policy limit.",
        explanation_bullets=[f"Total ₹{amount_inr} is below the ₹{limit} policy limit."],
    )


def check_user_confirmation(order: Order) -> PolicyDecision:
    """Section 5: REQUIRE_USER_CONFIRMATION - no payment without an explicit
    'yes' captured from the user, ever, regardless of what the agent infers."""
    if not settings.REQUIRE_USER_CONFIRMATION:
        return PolicyDecision(allowed=True, reason="Confirmation not required by policy.")
    if not order.user_confirmed:
        return PolicyDecision(
            allowed=False,
            reason="User has not explicitly confirmed this purchase.",
            explanation_bullets=[
                "Payment requires explicit user confirmation before it can proceed.",
                "The agent cannot infer consent from product interest alone.",
            ],
        )
    return PolicyDecision(
        allowed=True,
        reason="User explicitly confirmed the purchase.",
        explanation_bullets=["User explicitly confirmed."],
    )


def check_order_creation_allowed(db: Session, order: Order) -> PolicyDecision:
    """Section 7: idempotency guard. An order may only mint ONE Razorpay
    order (MAX_ORDER_CREATION_ATTEMPTS), enforced via idempotency_key/Payment
    row existence rather than trusting the caller not to double-submit."""
    existing_payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    if existing_payment is not None:
        return PolicyDecision(
            allowed=False,
            reason="A Razorpay order already exists for this PayPilot order; reusing it instead of creating a new one.",
            explanation_bullets=[
                "An existing payment record was found for this order.",
                "Re-using the existing Razorpay order prevents duplicate charges.",
            ],
        )
    return PolicyDecision(allowed=True, reason="No prior Razorpay order exists; safe to create one.")


def check_retry_allowed(db: Session, payment: Payment) -> PolicyDecision:
    """Section 12: bounded retries. Stops the user (and the agent) from
    retrying forever after repeated failures."""
    attempt_count = (
        db.query(PaymentAttempt).filter(PaymentAttempt.payment_id == payment.id).count()
    )
    limit = settings.MAX_PAYMENT_RETRY_ATTEMPTS
    if attempt_count >= limit:
        return PolicyDecision(
            allowed=False,
            reason=f"Maximum retry attempts ({limit}) reached for this order.",
            explanation_bullets=[
                f"{attempt_count} attempt(s) already made; the policy limit is {limit}.",
                "Further automatic retries are blocked; escalate to manual support.",
            ],
        )
    remaining = limit - attempt_count
    return PolicyDecision(
        allowed=True,
        reason=f"{remaining} retry attempt(s) remaining.",
        explanation_bullets=[f"{remaining} of {limit} retry attempts remaining."],
    )


def check_upsell_auto_add(is_agent_initiated: bool) -> PolicyDecision:
    """Section 10: the agent may SUGGEST an upsell but ALLOW_AUTOMATIC_UPSELL
    gates whether it may ever be added without the user saying yes."""
    if is_agent_initiated and not settings.ALLOW_AUTOMATIC_UPSELL:
        return PolicyDecision(
            allowed=False,
            reason="Automatic upsell addition is disabled by policy; user approval required.",
            explanation_bullets=["ALLOW_AUTOMATIC_UPSELL is false - the user must explicitly approve."],
        )
    return PolicyDecision(allowed=True, reason="Upsell addition allowed.")


def check_automatic_payment(is_agent_initiated: bool) -> PolicyDecision:
    """Section 5: the agent can never trigger a payment charge on its own."""
    if is_agent_initiated and not settings.ALLOW_AUTOMATIC_PAYMENT:
        return PolicyDecision(
            allowed=False,
            reason="Automatic payment execution is disabled by policy.",
            explanation_bullets=[
                "ALLOW_AUTOMATIC_PAYMENT is false.",
                "Only an explicit user action can trigger a real charge.",
            ],
        )
    return PolicyDecision(allowed=True, reason="Payment execution allowed.")


def explain_allowed_payment(order: Order) -> list[str]:
    return [
        "User explicitly confirmed.",
        f"Total ₹{order.total_amount} is below the ₹{settings.MAX_TRANSACTION_AMOUNT_INR} policy limit.",
        f"Order is in {order.status.value if hasattr(order.status, 'value') else order.status} state.",
    ]
