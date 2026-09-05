"""
Agent orchestrator.

This module IS the "agent" in the agentic-commerce sense: it decides which
bounded tool (app/agent/tools.py) to call next, in response to a natural
language message, and turns tool outputs into a conversational reply.

Two NLU modes:
  - LOCAL_RULES (default, no API key needed): deterministic regex/keyword
    parsing. Fully offline, fully reproducible, zero latency/cost - ideal
    for a hackathon demo that must never fail because of a flaky external
    LLM call.
  - LLM (if ANTHROPIC_API_KEY set): the same tool functions can be exposed to
    Claude via tool-calling; Claude only *proposes* which tool to call and
    with what arguments - execution and policy enforcement are identical
    either way.

In both modes, the actual money-moving decisions flow through app/policy.py.
The agent can suggest, but the backend decides.
"""
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app import policy
from app.audit import record_event
from app.config import settings
from app.models import ActorType, AgentSession, Order
from app.schemas import ChatMessageOut
from app.services import cart_service, order_service, payment_service, product_service
from app.agent import tools


# ---------------------------------------------------------------------------
# NLU helpers (LOCAL_RULES mode)
# ---------------------------------------------------------------------------
COLOR_WORDS = ["black", "white", "red", "blue", "grey", "gray", "green"]
CATEGORY_HINTS = {
    "shoe": "footwear", "shoes": "footwear", "footwear": "footwear",
    "sock": "accessories", "socks": "accessories",
    "watch": "electronics", "jacket": "apparel", "shirt": "apparel", "tee": "apparel",
    "bottle": "accessories", "insole": "accessories",
}
AFFIRM_WORDS = {"yes", "yep", "yeah", "sure", "confirm", "ok", "okay", "proceed", "add it",
                "add", "go ahead", "y", "please add", "do it"}
NEGATIVE_WORDS = {"no", "nope", "not now", "cancel", "skip", "n"}
CHECKOUT_WORDS = {"checkout", "pay", "payment", "buy", "purchase", "proceed to pay",
                   "proceed with payment", "place order"}
RETRY_WORDS = {"retry", "try again", "retry payment"}


def parse_budget(msg: str) -> int | None:
    m = re.search(r"under\s*(?:\u20b9|rs\.?|inr)?\s*(\d{2,6})", msg, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:\u20b9|rs\.?|inr)\s*(\d{2,6})", msg, re.I)
    if m:
        return int(m.group(1))
    return None


def parse_color(msg: str) -> str | None:
    msg_l = msg.lower()
    for c in COLOR_WORDS:
        if c in msg_l:
            return "grey" if c == "gray" else c
    return None


def parse_category(msg: str) -> str | None:
    msg_l = msg.lower()
    for k, v in CATEGORY_HINTS.items():
        if k in msg_l:
            return v
    return None


def parse_query_terms(msg: str) -> str:
    stop = {"i", "need", "want", "a", "the", "for", "under", "some", "show", "me", "add", "it"}
    words = [w for w in re.findall(r"[a-zA-Z]+", msg.lower()) if w not in stop]
    return " ".join(words)


def is_affirmative(msg: str) -> bool:
    m = msg.strip().lower()
    return m in AFFIRM_WORDS or any(m.startswith(w) for w in AFFIRM_WORDS)


def is_negative(msg: str) -> bool:
    m = msg.strip().lower()
    return m in NEGATIVE_WORDS or any(m.startswith(w) for w in NEGATIVE_WORDS)


def wants_checkout(msg: str) -> bool:
    m = msg.lower()
    return any(w in m for w in CHECKOUT_WORDS)


def wants_retry(msg: str) -> bool:
    m = msg.lower()
    return any(w in m for w in RETRY_WORDS)


def parse_ordinal_selection(msg: str) -> int | None:
    m = msg.lower()
    ordinals = {"first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2}
    for k, v in ordinals.items():
        if k in m:
            return v
    return None


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------
def get_or_create_session(db: Session, session_id: str | None, user_id: str, demo_scenario: str | None) -> AgentSession:
    if session_id:
        sess = db.get(AgentSession, session_id)
        if sess:
            return sess
    sess = AgentSession(user_id=user_id, demo_scenario=demo_scenario, state={})
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def save_state(db: Session, sess: AgentSession, **updates) -> None:
    state = dict(sess.state or {})
    state.update(updates)
    sess.state = state
    db.commit()


# ---------------------------------------------------------------------------
# Main turn handler
# ---------------------------------------------------------------------------
@dataclass
class TurnResult:
    messages: list[ChatMessageOut] = field(default_factory=list)
    order_id: str | None = None


def handle_turn(db: Session, sess: AgentSession, user_id: str, message: str) -> TurnResult:
    state = dict(sess.state or {})
    result = TurnResult()

    # ---- 0. Internal sentinel used by the frontend after a failed payment ----
    if message.strip() == "__mark_awaiting_retry__":
        save_state(db, sess, awaiting_retry=True)
        return result  # no visible chat message; UI already showed the retry prompt

    # ---- 1. Awaiting payment retry decision ----
    if state.get("awaiting_retry") and wants_retry(message):
        return _handle_retry(db, sess, state, result)

    # ---- 2. Awaiting explicit checkout confirmation (the safety gate) ----
    if state.get("awaiting_checkout_confirmation"):
        if is_affirmative(message):
            return _handle_checkout_confirmed(db, sess, state, result)
        if is_negative(message):
            state["awaiting_checkout_confirmation"] = False
            save_state(db, sess, **state)
            result.messages.append(ChatMessageOut(role="assistant",
                text="No problem - your cart is saved. Let me know whenever you'd like to checkout."))
            return result

    # ---- 3. Awaiting upsell approval ----
    if state.get("pending_upsell_id"):
        if is_affirmative(message):
            return _handle_upsell_accept(db, sess, state, result)
        if is_negative(message):
            state["pending_upsell_id"] = None
            save_state(db, sess, **state)
            cart = cart_service.get_or_create_cart(db, user_id, sess.id)
            cart_out = cart_service.to_cart_out(cart)
            result.messages.append(ChatMessageOut(role="assistant",
                text=f"No problem. Your cart total is \u20b9{cart_out.total}.", cart=cart_out))
            return result

    # ---- 4. Explicit checkout intent ----
    if wants_checkout(message):
        return _handle_checkout_intent(db, sess, state, user_id, result)

    # ---- 5. "add it" / add-to-cart intent referencing last shown product ----
    if any(w in message.lower() for w in ["add it", "add this", "add to cart"]) or message.strip().lower() == "add":
        return _handle_add_focus_product(db, sess, state, user_id, result)

    # ---- 6. Ordinal selection referencing last search results ----
    ordinal = parse_ordinal_selection(message)
    if ordinal is not None and state.get("last_results"):
        return _handle_show_details(db, sess, state, ordinal, result)

    # ---- 7. Default: treat as a product discovery / search request ----
    return _handle_search(db, sess, state, user_id, message, result)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def _handle_search(db, sess, state, user_id, message, result: TurnResult) -> TurnResult:
    budget = parse_budget(message)
    color = parse_color(message)
    category = parse_category(message)
    query = parse_query_terms(message)

    products = tools.tool_recommend_products(
        db, sess.id, query=query, max_price=budget, color=color, category=category, limit=3,
    )
    record_event(db, event_type="USER_REQUEST", actor=ActorType.USER, session_id=sess.id,
                 reason=message)
    record_event(db, event_type="PRODUCT_SEARCH", actor=ActorType.AGENT, session_id=sess.id,
                 reason=f"query='{query}' budget={budget} color={color} category={category}")

    if not products:
        result.messages.append(ChatMessageOut(role="assistant",
            text="I couldn't find anything matching that in the catalog. Could you try a different budget or category?"))
        return result

    save_state(db, sess, last_results=[p["id"] for p in products], last_focus=products[0]["id"],
               pending_upsell_id=None, awaiting_checkout_confirmation=False)

    lines = [f"Got it. I found {len(products)} option(s):"]
    for i, p in enumerate(products):
        why = "; ".join(p["why"])
        lines.append(f"{i+1}. {p['name']} - \u20b9{p['price']} ({why})")
    lines.append("Tell me which one you'd like (e.g. \"show me the first one\") or \"add it\" for the top pick.")

    for p in products:
        record_event(db, event_type="RECOMMENDATION", actor=ActorType.AGENT, session_id=sess.id,
                     amount=p["price"], reason=f"Product {p['id']}: " + "; ".join(p["why"]))

    from app.schemas import ProductOut
    result.messages.append(ChatMessageOut(role="assistant", text="\n".join(lines),
                                           product_cards=[ProductOut(**p) for p in products]))
    return result


def _handle_show_details(db, sess, state, ordinal, result: TurnResult) -> TurnResult:
    ids = state.get("last_results", [])
    if ordinal >= len(ids):
        result.messages.append(ChatMessageOut(role="assistant", text="I don't have that many options - could you pick again?"))
        return result
    product_id = ids[ordinal]
    p = tools.tool_get_product_details(db, sess.id, product_id)
    if not p:
        result.messages.append(ChatMessageOut(role="assistant", text="That product is no longer available."))
        return result
    save_state(db, sess, last_focus=product_id)
    from app.schemas import ProductOut
    text = (f"{p['name']} - \u20b9{p['price']}\n{p['description']}\n"
            f"Features: {', '.join(p['features'])}\nReturn policy: {p['return_policy']}\n"
            "Say \"add it\" to add this to your cart.")
    result.messages.append(ChatMessageOut(role="assistant", text=text, product_cards=[ProductOut(**p)]))
    return result


def _handle_add_focus_product(db, sess, state, user_id, result: TurnResult) -> TurnResult:
    product_id = state.get("last_focus")
    if not product_id:
        result.messages.append(ChatMessageOut(role="assistant",
            text="I'm not sure which product you mean yet - tell me what you're looking for first."))
        return result

    add_result = tools.tool_add_to_cart(db, sess.id, user_id, product_id, quantity=1, is_upsell=False)
    if not add_result["success"]:
        result.messages.append(ChatMessageOut(role="assistant",
            text=f"Couldn't add that to your cart: {add_result['reason']}"))
        return result

    cart = cart_service.get_or_create_cart(db, user_id, sess.id)
    cart_out = cart_service.to_cart_out(cart)
    product = product_service.get_product(db, product_id)

    lines = [f"Added {product.name} to your cart. Your cart is now \u20b9{cart_out.total}."]

    upsells = product_service.get_upsell_candidates(db, product)
    pending_upsell_id = None
    if upsells:
        up = upsells[0]
        already_in_cart = any(i.product_id == up.id for i in cart.items)
        if not already_in_cart:
            pending_upsell_id = up.id
            lines.append(f"Would you also like {up.name} for \u20b9{up.price}? It's commonly purchased with this item.")
            record_event(db, event_type="UPSELL_SUGGESTED", actor=ActorType.AGENT, session_id=sess.id,
                         order_id=None, amount=up.price, reason=f"Suggested {up.id} alongside {product.id}")

    save_state(db, sess, pending_upsell_id=pending_upsell_id)
    result.messages.append(ChatMessageOut(role="assistant", text="\n".join(lines), cart=cart_out))
    return result


def _handle_upsell_accept(db, sess, state, result: TurnResult) -> TurnResult:
    upsell_id = state["pending_upsell_id"]
    user_id = sess.user_id
    tools.tool_add_to_cart(db, sess.id, user_id, upsell_id, quantity=1, is_upsell=True)
    cart = cart_service.get_or_create_cart(db, user_id, sess.id)
    cart_out = cart_service.to_cart_out(cart)

    record_event(db, event_type="UPSELL_ACCEPTED", actor=ActorType.USER, session_id=sess.id,
                 amount=cart_out.upsell_amount, reason=f"User accepted upsell {upsell_id}")

    save_state(db, sess, pending_upsell_id=None)
    result.messages.append(ChatMessageOut(
        role="assistant",
        text=f"Great choice! Your cart is now \u20b9{cart_out.total}. Say \"checkout\" whenever you're ready to pay.",
        cart=cart_out,
    ))
    return result


def _handle_checkout_intent(db, sess, state, user_id, result: TurnResult) -> TurnResult:
    cart = cart_service.get_or_create_cart(db, user_id, sess.id)
    if not cart.items:
        result.messages.append(ChatMessageOut(role="assistant", text="Your cart is empty - let's find something first!"))
        return result

    order = order_service.get_or_create_order_from_cart(db, cart, user_id, sess.id)
    decision = order_service.validate_checkout(db, order)

    if not decision.allowed:
        result.messages.append(ChatMessageOut(
            role="assistant",
            text="Payment blocked because:\n\u2022 " + "\n\u2022 ".join(decision.explanation_bullets),
            policy_notice=decision.as_dict(),
        ))
        result.order_id = order.id
        return result

    save_state(db, sess, awaiting_checkout_confirmation=True, order_id=order.id)
    cart_out = cart_service.to_cart_out(cart)
    result.messages.append(ChatMessageOut(
        role="assistant",
        text=(f"Your total is \u20b9{cart_out.total}. Payment requires your explicit confirmation through "
              "Razorpay Checkout. Would you like to proceed with payment?"),
        cart=cart_out,
        ui_action="SHOW_CHECKOUT_GATE",
    ))
    result.order_id = order.id
    return result


def _handle_checkout_confirmed(db, sess, state, result: TurnResult) -> TurnResult:
    order_id = state["order_id"]
    order = db.get(Order, order_id)
    order = order_service.confirm_order(db, order)

    try:
        payment = payment_service.create_payment_for_order(db, order, actor=ActorType.USER)
    except payment_service.PolicyBlockedError as e:
        save_state(db, sess, awaiting_checkout_confirmation=False)
        result.messages.append(ChatMessageOut(
            role="assistant",
            text="Payment blocked because:\n\u2022 " + "\n\u2022 ".join(e.decision.explanation_bullets),
            policy_notice=e.decision.as_dict(),
        ))
        result.order_id = order.id
        return result

    save_state(db, sess, awaiting_checkout_confirmation=False, order_id=order.id)
    from app.services.razorpay_client import gateway as rp_gateway
    checkout_payload = {
        "razorpay_order_id": payment.razorpay_order_id,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID or "rzp_test_mock_key",
        "amount_paise": payment.amount * 100,
        "currency": payment.currency,
        "order_id": order.id,
        "is_mock": rp_gateway.is_mock,
    }
    record_event(db, event_type="PAYMENT_INITIATED", actor=ActorType.USER, order_id=order.id,
                 amount=order.total_amount, reason="Razorpay Checkout launched for user.")

    result.messages.append(ChatMessageOut(
        role="assistant",
        text=f"Opening secure Razorpay Checkout to complete your payment of \u20b9{order.total_amount}.",
        ui_action="LAUNCH_PAYMENT",
        checkout_payload=checkout_payload,
    ))
    result.order_id = order.id
    return result


def _handle_retry(db, sess, state, result: TurnResult) -> TurnResult:
    order_id = state.get("order_id")
    order = db.get(Order, order_id)
    from app.models import Payment
    payment = db.query(Payment).filter(Payment.order_id == order.id).first()
    decision = policy.check_retry_allowed(db, payment)
    save_state(db, sess, awaiting_retry=False)
    if not decision.allowed:
        result.messages.append(ChatMessageOut(role="assistant",
            text="Payment could not be completed after the allowed attempts. Please try another payment method or contact support."))
        return result

    from app.services.razorpay_client import gateway as rp_gateway
    checkout_payload = {
        "razorpay_order_id": payment.razorpay_order_id,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID or "rzp_test_mock_key",
        "amount_paise": payment.amount * 100,
        "currency": payment.currency,
        "order_id": order.id,
        "is_mock": rp_gateway.is_mock,
    }
    result.messages.append(ChatMessageOut(
        role="assistant", text="Retrying payment - opening Razorpay Checkout again.",
        ui_action="LAUNCH_PAYMENT", checkout_payload=checkout_payload,
    ))
    result.order_id = order.id
    return result


def mark_awaiting_retry(db: Session, sess: AgentSession) -> None:
    save_state(db, sess, awaiting_retry=True)
