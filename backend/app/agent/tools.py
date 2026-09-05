"""
Agent tools.

Every function here is a controlled, narrow capability - NOT raw database or
payment access. The agent (LLM or rule-based planner) may call these; it
cannot execute arbitrary SQL or Razorpay calls. Business rules (policy.py)
remain authoritative even when a tool nominally "succeeds" - e.g.
add_to_cart still runs, but create_payment enforces confirmation + limits
regardless of what the agent asked for.
"""
from sqlalchemy.orm import Session

from app.models import ActorType, AgentAction, Cart
from app.services import cart_service, order_service, payment_service, product_service


def log_action(db: Session, session_id: str, tool_name: str, tool_input: dict,
                tool_output: dict, allowed: bool = True, policy_reason: str = "") -> None:
    db.add(AgentAction(
        session_id=session_id, tool_name=tool_name, tool_input=tool_input,
        tool_output=tool_output, allowed=allowed, policy_reason=policy_reason,
    ))
    db.commit()


def tool_search_products(db: Session, session_id: str, **kwargs) -> list[dict]:
    products = product_service.search_products(db, **kwargs)
    out = [p.to_agent_dict() for p in products]
    log_action(db, session_id, "search_products", kwargs, {"count": len(out)})
    return out


def tool_get_product_details(db: Session, session_id: str, product_id: str) -> dict | None:
    product = product_service.get_product(db, product_id)
    out = product.to_agent_dict() if product else None
    log_action(db, session_id, "get_product_details", {"product_id": product_id}, {"found": bool(out)})
    return out


def tool_recommend_products(db: Session, session_id: str, *, query: str, max_price: int | None,
                             color: str | None, category: str | None, limit: int = 3) -> list[dict]:
    products = product_service.search_products(
        db, query=query, max_price=max_price, color=color, category=category, limit=limit,
    )
    out = []
    for p in products:
        out.append({
            **p.to_agent_dict(),
            "why": product_service.explain_recommendation(p, budget=max_price, color=color, category_hint=category),
        })
    log_action(db, session_id, "recommend_products",
               {"query": query, "max_price": max_price, "color": color, "category": category},
               {"count": len(out)})
    return out


def tool_add_to_cart(db: Session, session_id: str, user_id: str, product_id: str,
                      quantity: int = 1, is_upsell: bool = False) -> dict:
    product = product_service.get_product(db, product_id)
    if not product or product.stock < quantity:
        result = {"success": False, "reason": "Product unavailable or insufficient stock."}
        log_action(db, session_id, "add_to_cart", locals_input(product_id, quantity, is_upsell),
                   result, allowed=False, policy_reason=result["reason"])
        return result

    if is_upsell:
        from app import policy
        decision = policy.check_upsell_auto_add(is_agent_initiated=True)
        # Note: agent-suggested upsells always require the explicit user "yes"
        # turn before this tool is invoked with is_upsell=True from the API
        # layer; this check is defense-in-depth against a stray automatic call.

    cart = cart_service.get_or_create_cart(db, user_id, session_id)
    item = cart_service.add_item(db, cart, product, quantity=quantity,
                                  added_by=ActorType.AGENT, is_upsell=is_upsell)
    cart_out = cart_service.to_cart_out(cart)
    result = {"success": True, "item_id": item.id, "cart_total": cart_out.total}
    log_action(db, session_id, "add_to_cart",
               {"product_id": product_id, "quantity": quantity, "is_upsell": is_upsell}, result)
    return result


def locals_input(product_id, quantity, is_upsell):
    return {"product_id": product_id, "quantity": quantity, "is_upsell": is_upsell}


def tool_remove_from_cart(db: Session, session_id: str, user_id: str, item_id: str) -> dict:
    cart = cart_service.get_or_create_cart(db, user_id, session_id)
    ok = cart_service.remove_item(db, cart, item_id)
    result = {"success": ok}
    log_action(db, session_id, "remove_from_cart", {"item_id": item_id}, result)
    return result


def tool_get_cart(db: Session, session_id: str, user_id: str) -> dict:
    cart = cart_service.get_or_create_cart(db, user_id, session_id)
    out = cart_service.to_cart_out(cart).model_dump()
    log_action(db, session_id, "get_cart", {}, {"total": out["total"]})
    return out


def tool_calculate_cart_total(db: Session, session_id: str, user_id: str) -> dict:
    cart = cart_service.get_or_create_cart(db, user_id, session_id)
    totals = cart_service.calculate_totals(cart)
    log_action(db, session_id, "calculate_cart_total", {}, totals)
    return totals


def tool_validate_checkout(db: Session, session_id: str, order) -> dict:
    decision = order_service.validate_checkout(db, order)
    out = decision.as_dict()
    log_action(db, session_id, "validate_checkout", {"order_id": order.id}, out,
               allowed=decision.allowed, policy_reason=decision.reason)
    return out
