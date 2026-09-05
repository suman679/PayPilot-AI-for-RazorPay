from sqlalchemy.orm import Session

from app.models import AuditEvent, Order, OrderStatus, PaymentAttempt


def compute_analytics(db: Session) -> dict:
    """Computed ONLY from real Order/Payment/AuditEvent rows - i.e. actual
    Razorpay TEST MODE activity that happened in this running instance.
    Never mixed with SimulationRun data (see section 15 / simulation.py)."""
    orders = db.query(Order).all()
    paid_orders = [o for o in orders if o.status == OrderStatus.PAID]

    gmv = sum(o.total_amount for o in paid_orders)
    ai_assisted_orders = [o for o in paid_orders if o.session_id]
    ai_assisted_gmv = sum(o.total_amount for o in ai_assisted_orders)

    upsell_impressions = db.query(AuditEvent).filter(AuditEvent.event_type == "UPSELL_SUGGESTED").count()
    upsell_accepted = db.query(AuditEvent).filter(AuditEvent.event_type == "UPSELL_ACCEPTED").count()
    upsell_rate = (upsell_accepted / upsell_impressions * 100) if upsell_impressions else 0.0

    avg_order_value = (gmv / len(paid_orders)) if paid_orders else 0.0

    attempts = db.query(PaymentAttempt).all()
    success_attempts = [a for a in attempts if a.result == "SUCCESS"]
    payment_success_rate = (len(success_attempts) / len(attempts) * 100) if attempts else 0.0
    payment_failures = len([a for a in attempts if a.result == "FAILED"])

    blocked_actions = db.query(AuditEvent).filter(AuditEvent.result == "BLOCKED").count()

    product_counts: dict[str, dict] = {}
    for o in paid_orders:
        for item in o.items:
            entry = product_counts.setdefault(item.product_id, {"name": item.product_name, "qty": 0, "revenue": 0})
            entry["qty"] += item.quantity
            entry["revenue"] += item.unit_price * item.quantity
    top_products = sorted(
        [{"product_id": k, **v} for k, v in product_counts.items()],
        key=lambda x: x["revenue"], reverse=True,
    )[:5]

    recent_orders = [
        {"id": o.id, "status": o.status.value, "total_amount": o.total_amount,
         "created_at": o.created_at.isoformat()}
        for o in sorted(orders, key=lambda o: o.created_at, reverse=True)[:10]
    ]

    return {
        "gmv": gmv,
        "ai_assisted_gmv": ai_assisted_gmv,
        "total_orders": len(paid_orders),
        "ai_assisted_orders": len(ai_assisted_orders),
        "upsell_impressions": upsell_impressions,
        "upsell_accepted": upsell_accepted,
        "upsell_acceptance_rate": round(upsell_rate, 1),
        "average_order_value": round(avg_order_value, 2),
        "payment_success_rate": round(payment_success_rate, 1),
        "payment_failures": payment_failures,
        "blocked_actions": blocked_actions,
        "top_products": top_products,
        "recent_orders": recent_orders,
    }
