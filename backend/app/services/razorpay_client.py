"""
Razorpay client wrapper.

If RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set, we fall back to a mock
client so the project still runs end-to-end for local development without
credentials. Every mock-created object is tagged `is_mock=True` and every
audit event derived from it is prefixed "[SIMULATED]" so simulated activity
can never be mistaken for a real Razorpay TEST MODE transaction (section 23).
"""
import hmac
import hashlib
import uuid

import razorpay

from app.config import settings


class SignatureVerificationError(Exception):
    pass


class RazorpayGateway:
    def __init__(self):
        self.is_mock = not settings.razorpay_configured
        if not self.is_mock:
            self.client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        else:
            self.client = None

    # ---- Order creation ----
    def create_order(self, amount_paise: int, currency: str, receipt: str, notes: dict) -> dict:
        if self.is_mock:
            return {
                "id": f"order_MOCK{uuid.uuid4().hex[:14]}",
                "amount": amount_paise,
                "currency": currency,
                "receipt": receipt,
                "status": "created",
                "is_mock": True,
            }
        order = self.client.order.create({
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt,
            "notes": notes,
            "payment_capture": 1,
        })
        order["is_mock"] = False
        return order

    # ---- Signature verification (server-side, NEVER trust frontend state) ----
    def verify_payment_signature(self, params: dict) -> bool:
        """params must contain razorpay_order_id, razorpay_payment_id, razorpay_signature."""
        if self.is_mock:
            # Mock verification: signature must equal our own deterministic
            # HMAC so a forged/absent signature is still rejected.
            expected = self._mock_signature(params["razorpay_order_id"], params["razorpay_payment_id"])
            if params.get("razorpay_signature") != expected:
                raise SignatureVerificationError("Mock signature mismatch.")
            return True
        try:
            self.client.utility.verify_payment_signature(params)
            return True
        except razorpay.errors.SignatureVerificationError as e:
            raise SignatureVerificationError(str(e)) from e

    def _mock_signature(self, order_id: str, payment_id: str) -> str:
        secret = settings.RAZORPAY_KEY_SECRET or "mock_secret"
        msg = f"{order_id}|{payment_id}".encode()
        return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()

    # ---- Webhook signature verification ----
    def verify_webhook_signature(self, payload_body: bytes, signature: str) -> bool:
        if self.is_mock:
            expected = hmac.new(
                (settings.RAZORPAY_WEBHOOK_SECRET or "mock_webhook_secret").encode(),
                payload_body, hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, signature or "")
        try:
            self.client.utility.verify_webhook_signature(
                payload_body.decode(), signature, settings.RAZORPAY_WEBHOOK_SECRET
            )
            return True
        except Exception:
            return False


gateway = RazorpayGateway()
