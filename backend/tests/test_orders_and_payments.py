import pytest

from app.models import ActorType, Cart, Order, OrderStatus, Payment
from app.services import cart_service, order_service, payment_service, product_service
from app.services.razorpay_client import gateway


def _cart_with_shoe(db_session, session_id="sess_pay"):
    cart = Cart(user_id="user_test", session_id=session_id)
    db_session.add(cart)
    db_session.commit()
    shoe = product_service.get_product(db_session, "SHOE_102")
    cart_service.add_item(db_session, cart, shoe, quantity=1, added_by=ActorType.AGENT)
    return cart


def test_duplicate_checkout_reuses_same_order(db_session):
    cart = _cart_with_shoe(db_session)
    order1 = order_service.get_or_create_order_from_cart(db_session, cart, "user_test", "sess_pay")
    order2 = order_service.get_or_create_order_from_cart(db_session, cart, "user_test", "sess_pay")
    assert order1.id == order2.id


def test_payment_blocked_without_confirmation(db_session):
    cart = _cart_with_shoe(db_session)
    order = order_service.get_or_create_order_from_cart(db_session, cart, "user_test", "sess_pay")
    with pytest.raises(payment_service.PolicyBlockedError):
        payment_service.create_payment_for_order(db_session, order)


def test_payment_blocked_over_transaction_limit(db_session):
    cart = Cart(user_id="user_test", session_id="sess_big")
    db_session.add(cart)
    db_session.commit()
    watch = product_service.get_product(db_session, "WATCH_601")  # 8999 > 5000 limit
    cart_service.add_item(db_session, cart, watch, quantity=1)
    order = order_service.get_or_create_order_from_cart(db_session, cart, "user_test", "sess_big")
    order_service.confirm_order(db_session, order)
    with pytest.raises(payment_service.PolicyBlockedError):
        payment_service.create_payment_for_order(db_session, order)


def test_create_payment_is_idempotent(db_session):
    cart = _cart_with_shoe(db_session)
    order = order_service.get_or_create_order_from_cart(db_session, cart, "user_test", "sess_pay")
    order_service.confirm_order(db_session, order)

    payment1 = payment_service.create_payment_for_order(db_session, order)
    payment2 = payment_service.create_payment_for_order(db_session, order)
    assert payment1.id == payment2.id
    assert db_session.query(Payment).filter(Payment.order_id == order.id).count() == 1


def test_verify_payment_success_with_valid_signature(db_session):
    cart = _cart_with_shoe(db_session)
    order = order_service.get_or_create_order_from_cart(db_session, cart, "user_test", "sess_pay")
    order_service.confirm_order(db_session, order)
    payment = payment_service.create_payment_for_order(db_session, order)

    fake_payment_id = "pay_TESTFAKE123"
    valid_sig = gateway._mock_signature(payment.razorpay_order_id, fake_payment_id)

    success, message, retries = payment_service.verify_and_record_payment(
        db_session, order, payment,
        razorpay_order_id=payment.razorpay_order_id,
        razorpay_payment_id=fake_payment_id,
        razorpay_signature=valid_sig,
    )
    assert success is True
    assert order.status == OrderStatus.PAID


def test_verify_payment_fails_with_invalid_signature(db_session):
    cart = _cart_with_shoe(db_session, session_id="sess_pay2")
    order = order_service.get_or_create_order_from_cart(db_session, cart, "user_test", "sess_pay2")
    order_service.confirm_order(db_session, order)
    payment = payment_service.create_payment_for_order(db_session, order)

    success, message, retries = payment_service.verify_and_record_payment(
        db_session, order, payment,
        razorpay_order_id=payment.razorpay_order_id,
        razorpay_payment_id="pay_FAKE",
        razorpay_signature="not_a_real_signature",
    )
    assert success is False
    assert retries == 1  # one retry left out of MAX_PAYMENT_RETRY_ATTEMPTS=2


def test_retry_limit_stops_after_max_attempts(db_session):
    cart = _cart_with_shoe(db_session, session_id="sess_pay3")
    order = order_service.get_or_create_order_from_cart(db_session, cart, "user_test", "sess_pay3")
    order_service.confirm_order(db_session, order)
    payment = payment_service.create_payment_for_order(db_session, order)

    for _ in range(2):
        success, message, retries = payment_service.verify_and_record_payment(
            db_session, order, payment,
            razorpay_order_id=payment.razorpay_order_id,
            razorpay_payment_id="pay_FAKE",
            razorpay_signature="bad_signature",
        )
    assert success is False
    assert retries == 0
    assert order.status == OrderStatus.FAILED
    assert "could not be completed after the allowed attempts" in message
