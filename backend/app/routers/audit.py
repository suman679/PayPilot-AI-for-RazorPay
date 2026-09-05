from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit import get_trail_for_order
from app.database import get_db
from app.schemas import AuditEventOut

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/{order_id}", response_model=list[AuditEventOut])
def get_audit_trail(order_id: str, db: Session = Depends(get_db)):
    events = get_trail_for_order(db, order_id)
    return [
        AuditEventOut(
            id=e.id, timestamp=e.timestamp, event_type=e.event_type, actor=e.actor.value,
            order_id=e.order_id, amount=e.amount, reason=e.reason,
            previous_state=e.previous_state, new_state=e.new_state, result=e.result,
            event_metadata=e.event_metadata,
        )
        for e in events
    ]
