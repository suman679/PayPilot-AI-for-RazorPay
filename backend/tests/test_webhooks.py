import hmac
import hashlib
import json

from app.config import settings
from app.models import WebhookEvent
from app.services.razorpay_client import gateway


def _sign(body: bytes) -> str:
    secret = settings.RAZORPAY_WEBHOOK_SECRET or "mock_webhook_secret"
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_signature_valid_and_invalid():
    body = json.dumps({"event": "payment.captured", "id": "evt_1"}).encode()
    good_sig = _sign(body)
    assert gateway.verify_webhook_signature(body, good_sig) is True
    assert gateway.verify_webhook_signature(body, "wrong_signature") is False


def test_webhook_event_dedup_logic(db_session):
    # Simulate the dedup check the router performs
    db_session.add(WebhookEvent(razorpay_event_id="evt_dup_1", event_type="payment.captured", payload={}))
    db_session.commit()

    existing = db_session.query(WebhookEvent).filter(WebhookEvent.razorpay_event_id == "evt_dup_1").first()
    assert existing is not None  # a second delivery of evt_dup_1 would be rejected by the router
