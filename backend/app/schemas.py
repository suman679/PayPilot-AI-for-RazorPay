from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Products ----------
class ProductOut(BaseModel):
    id: str
    name: str
    description: str
    category: str
    price: int
    currency: str
    brand: str
    color: str
    sizes: list[str]
    stock: int
    tags: list[str]
    features: list[str]
    rating: float
    return_policy: str
    image_emoji: str

    class Config:
        from_attributes = True


# ---------- Cart ----------
class CartItemOut(BaseModel):
    id: str
    product: ProductOut
    quantity: int
    is_upsell: bool
    line_total: int


class CartOut(BaseModel):
    id: str
    items: list[CartItemOut]
    subtotal: int
    upsell_amount: int
    total: int


class AddToCartRequest(BaseModel):
    session_id: str
    product_id: str
    quantity: int = 1
    is_upsell: bool = False


# ---------- Chat / Agent ----------
class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str
    message: str
    demo_scenario: Optional[str] = None


class ChatMessageOut(BaseModel):
    role: str  # "assistant" | "system"
    text: str
    product_cards: list[ProductOut] = Field(default_factory=list)
    cart: Optional[CartOut] = None
    ui_action: Optional[str] = None  # e.g. "SHOW_CHECKOUT_GATE", "LAUNCH_PAYMENT"
    checkout_payload: Optional[dict[str, Any]] = None
    policy_notice: Optional[dict[str, Any]] = None


class ChatResponse(BaseModel):
    session_id: str
    order_id: Optional[str] = None
    messages: list[ChatMessageOut]


# ---------- Checkout / Orders ----------
class ValidateCheckoutRequest(BaseModel):
    session_id: str
    user_confirmed: bool = False


class CreateOrderRequest(BaseModel):
    session_id: str
    user_id: str


class OrderOut(BaseModel):
    id: str
    status: str
    subtotal: int
    upsell_amount: int
    total_amount: int
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- Payments ----------
class CreatePaymentRequest(BaseModel):
    order_id: str


class RazorpayOrderOut(BaseModel):
    razorpay_order_id: str
    razorpay_key_id: str
    amount_paise: int
    currency: str
    order_id: str
    prefill_name: str
    prefill_email: str


class VerifyPaymentRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class VerifyPaymentResponse(BaseModel):
    success: bool
    order_status: str
    message: str
    retries_remaining: int = 0


class RetryPaymentRequest(BaseModel):
    order_id: str


# ---------- Audit ----------
class AuditEventOut(BaseModel):
    id: str
    timestamp: datetime
    event_type: str
    actor: str
    order_id: Optional[str]
    amount: Optional[int]
    reason: str
    previous_state: Optional[str]
    new_state: Optional[str]
    result: str
    event_metadata: dict[str, Any]

    class Config:
        from_attributes = True


# ---------- Analytics ----------
class AnalyticsOut(BaseModel):
    gmv: int
    ai_assisted_gmv: int
    total_orders: int
    ai_assisted_orders: int
    upsell_impressions: int
    upsell_accepted: int
    upsell_acceptance_rate: float
    average_order_value: float
    payment_success_rate: float
    payment_failures: int
    blocked_actions: int
    top_products: list[dict[str, Any]]
    recent_orders: list[dict[str, Any]]
