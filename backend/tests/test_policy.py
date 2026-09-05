from app import policy
from app.models import Order, OrderStatus


def test_transaction_limit_blocks_over_limit_amount():
    decision = policy.check_transaction_limit(7000)
    assert decision.allowed is False
    assert "7000" in decision.reason


def test_transaction_limit_allows_under_limit_amount():
    decision = policy.check_transaction_limit(2998)
    assert decision.allowed is True


def test_confirmation_required_blocks_unconfirmed_order(db_session):
    order = Order(user_id="user_test", status=OrderStatus.PENDING_CONFIRMATION,
                   total_amount=1000, user_confirmed=False)
    db_session.add(order)
    db_session.commit()
    decision = policy.check_user_confirmation(order)
    assert decision.allowed is False


def test_confirmation_required_allows_confirmed_order(db_session):
    order = Order(user_id="user_test", status=OrderStatus.PENDING_CONFIRMATION,
                   total_amount=1000, user_confirmed=True)
    db_session.add(order)
    db_session.commit()
    decision = policy.check_user_confirmation(order)
    assert decision.allowed is True


def test_order_creation_blocked_if_payment_already_exists(db_session):
    from app.models import Payment, PaymentStatus
    order = Order(user_id="user_test", status=OrderStatus.PAYMENT_PENDING, total_amount=1000)
    db_session.add(order)
    db_session.commit()
    db_session.add(Payment(order_id=order.id, razorpay_order_id="order_ABC", amount=1000,
                            status=PaymentStatus.CREATED))
    db_session.commit()

    decision = policy.check_order_creation_allowed(db_session, order)
    assert decision.allowed is False


def test_retry_allowed_within_limit_and_blocked_beyond_it(db_session):
    from app.models import Payment, PaymentAttempt, PaymentStatus
    order = Order(user_id="user_test", status=OrderStatus.PAYMENT_PENDING, total_amount=1000)
    db_session.add(order)
    db_session.commit()
    payment = Payment(order_id=order.id, razorpay_order_id="order_XYZ", amount=1000,
                       status=PaymentStatus.CREATED)
    db_session.add(payment)
    db_session.commit()

    decision = policy.check_retry_allowed(db_session, payment)
    assert decision.allowed is True  # 0 attempts so far, limit is 2

    db_session.add(PaymentAttempt(payment_id=payment.id, attempt_number=1, result="FAILED"))
    db_session.add(PaymentAttempt(payment_id=payment.id, attempt_number=2, result="FAILED"))
    db_session.commit()

    decision = policy.check_retry_allowed(db_session, payment)
    assert decision.allowed is False
