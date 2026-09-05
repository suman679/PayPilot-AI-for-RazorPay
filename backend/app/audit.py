"""
Audit trail service.

Design rule: rows are only ever INSERTed, never UPDATEd or DELETEd. Every
service that touches money, policy decisions, or agent tool calls must
record an event here. This file has no business logic of its own - it is a
dumb, reliable recorder, which is what makes it trustworthy.
"""
from sqlalchemy.orm import Session

from app.models import ActorType, AuditEvent


def record_event(
    db: Session,
    *,
    event_type: str,
    actor: ActorType = ActorType.SYSTEM,
    order_id: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    amount: int | None = None,
    reason: str = "",
    previous_state: str | None = None,
    new_state: str | None = None,
    result: str = "OK",
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        event_type=event_type,
        actor=actor,
        order_id=order_id,
        user_id=user_id,
        session_id=session_id,
        amount=amount,
        reason=reason,
        previous_state=previous_state,
        new_state=new_state,
        result=result,
        event_metadata=metadata or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_trail_for_order(db: Session, order_id: str) -> list[AuditEvent]:
    return (
        db.query(AuditEvent)
        .filter(AuditEvent.order_id == order_id)
        .order_by(AuditEvent.timestamp.asc())
        .all()
    )
