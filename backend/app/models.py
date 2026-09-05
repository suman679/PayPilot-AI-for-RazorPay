import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ----------------------------------------------------------------------------
# Enums - explicit state machines. State transitions are enforced in services,
# never inferred implicitly, so every state change is intentional and audited.
# ----------------------------------------------------------------------------
class OrderStatus(str, enum.Enum):
    CART = "CART"                          # not yet checked out
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"  # awaiting explicit user "yes"
    PAYMENT_PENDING = "PAYMENT_PENDING"    # razorpay order created, awaiting payment
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    CREATED = "CREATED"
    ATTEMPTED = "ATTEMPTED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class ActorType(str, enum.Enum):
    USER = "USER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
    WEBHOOK = "WEBHOOK"


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: gen_id("user"))
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    carts = relationship("Cart", back_populates="user")
    orders = relationship("Order", back_populates="user")


class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True)  # human-readable catalog id e.g. SHOE_102
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, index=True)
    price = Column(Integer, nullable=False)  # INR, whole rupees
    currency = Column(String, default="INR")
    brand = Column(String, default="")
    color = Column(String, default="")
    sizes = Column(JSON, default=list)
    stock = Column(Integer, default=0)
    tags = Column(JSON, default=list)
    features = Column(JSON, default=list)
    rating = Column(Float, default=4.5)
    return_policy = Column(String, default="7-day returns")
    upsell_products = Column(JSON, default=list)     # list of product ids
    cross_sell_products = Column(JSON, default=list)  # list of product ids
    image_emoji = Column(String, default="\U0001F4E6")  # package emoji fallback

    def to_agent_dict(self) -> dict:
        """Structured, agent-readable representation. This is the ONLY product
        data the LLM ever sees - it cannot hallucinate fields that aren't here."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "price": self.price,
            "currency": self.currency,
            "brand": self.brand,
            "color": self.color,
            "sizes": self.sizes,
            "stock": self.stock,
            "in_stock": self.stock > 0,
            "tags": self.tags,
            "features": self.features,
            "rating": self.rating,
            "return_policy": self.return_policy,
            "image_emoji": self.image_emoji,
        }


class Cart(Base):
    __tablename__ = "carts"
    id = Column(String, primary_key=True, default=lambda: gen_id("cart"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, ForeignKey("agent_sessions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="carts")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(String, primary_key=True, default=lambda: gen_id("item"))
    cart_id = Column(String, ForeignKey("carts.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1)
    added_by = Column(Enum(ActorType), default=ActorType.AGENT)
    is_upsell = Column(Boolean, default=False)

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")


class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True, default=lambda: gen_id("order"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, ForeignKey("agent_sessions.id"), nullable=True)
    status = Column(Enum(OrderStatus), default=OrderStatus.CART, index=True)
    subtotal = Column(Integer, default=0)
    upsell_amount = Column(Integer, default=0)
    total_amount = Column(Integer, default=0)
    currency = Column(String, default="INR")
    idempotency_key = Column(String, unique=True, index=True)  # one Razorpay order per idempotency key
    user_confirmed = Column(Boolean, default=False)
    user_confirmed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(String, primary_key=True, default=lambda: gen_id("oitem"))
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    product_name = Column(String)  # snapshot - survives catalog changes
    unit_price = Column(Integer)
    quantity = Column(Integer, default=1)
    is_upsell = Column(Boolean, default=False)

    order = relationship("Order", back_populates="items")


class Payment(Base):
    """One row per Razorpay order created for a PayPilot order. Idempotency is
    enforced upstream (Order.idempotency_key) so retries reuse this row rather
    than creating a new Razorpay order."""
    __tablename__ = "payments"
    id = Column(String, primary_key=True, default=lambda: gen_id("pay"))
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    razorpay_order_id = Column(String, unique=True, index=True)
    razorpay_payment_id = Column(String, nullable=True)
    razorpay_signature = Column(String, nullable=True)
    amount = Column(Integer, nullable=False)  # rupees
    currency = Column(String, default="INR")
    status = Column(Enum(PaymentStatus), default=PaymentStatus.CREATED)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)

    order = relationship("Order", back_populates="payments")
    attempts = relationship("PaymentAttempt", back_populates="payment", cascade="all, delete-orphan")


class PaymentAttempt(Base):
    """Every attempt to pay (success or fail) against a Payment/Razorpay order.
    Used to enforce MAX_PAYMENT_RETRY_ATTEMPTS and for the audit trail."""
    __tablename__ = "payment_attempts"
    id = Column(String, primary_key=True, default=lambda: gen_id("attempt"))
    payment_id = Column(String, ForeignKey("payments.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    result = Column(String)  # SUCCESS | FAILED
    failure_reason = Column(String, nullable=True)
    raw_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    payment = relationship("Payment", back_populates="attempts")


class WebhookEvent(Base):
    """Dedup log for Razorpay webhooks - the (event_id) is unique so the same
    webhook delivery can never be processed twice."""
    __tablename__ = "webhook_events"
    id = Column(String, primary_key=True, default=lambda: gen_id("wh"))
    razorpay_event_id = Column(String, unique=True, index=True, nullable=True)
    event_type = Column(String)
    payload = Column(JSON, default=dict)
    processed_at = Column(DateTime, default=datetime.utcnow)


class AuditEvent(Base):
    """Immutable-style audit log. Rows are never updated or deleted - only
    inserted - so the trail is a faithful, append-only history."""
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True, default=lambda: gen_id("audit"))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    event_type = Column(String, index=True)
    actor = Column(Enum(ActorType), default=ActorType.SYSTEM)
    order_id = Column(String, ForeignKey("orders.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    session_id = Column(String, nullable=True)
    amount = Column(Integer, nullable=True)
    reason = Column(Text, default="")
    previous_state = Column(String, nullable=True)
    new_state = Column(String, nullable=True)
    result = Column(String, default="OK")  # OK | BLOCKED | ERROR
    event_metadata = Column(JSON, default=dict)


class AgentSession(Base):
    __tablename__ = "agent_sessions"
    id = Column(String, primary_key=True, default=lambda: gen_id("sess"))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    demo_scenario = Column(String, nullable=True)  # tags DEMO MODE sessions
    state = Column(JSON, default=dict)  # small conversation-state scratchpad (see agent/agent.py)

    actions = relationship("AgentAction", back_populates="session", cascade="all, delete-orphan")


class AgentAction(Base):
    """Every tool call the LLM/agent makes, with backend-decided outcome. This
    is the record that proves the backend - not the model - is authoritative."""
    __tablename__ = "agent_actions"
    id = Column(String, primary_key=True, default=lambda: gen_id("act"))
    session_id = Column(String, ForeignKey("agent_sessions.id"), nullable=False)
    tool_name = Column(String, index=True)
    tool_input = Column(JSON, default=dict)
    tool_output = Column(JSON, default=dict)
    allowed = Column(Boolean, default=True)
    policy_reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("AgentSession", back_populates="actions")


class SimulationRun(Base):
    """Stores results of the synthetic batch-session evaluation (section 15).
    Clearly separated table so simulated metrics can NEVER be confused with
    real orders/payments."""
    __tablename__ = "simulation_runs"
    id = Column(String, primary_key=True, default=lambda: gen_id("sim"))
    created_at = Column(DateTime, default=datetime.utcnow)
    num_sessions = Column(Integer)
    results = Column(JSON, default=dict)