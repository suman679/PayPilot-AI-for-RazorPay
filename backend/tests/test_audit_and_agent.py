from app.audit import get_trail_for_order, record_event
from app.models import ActorType, AgentSession
from app.agent import agent


def test_record_event_creates_row(db_session):
    event = record_event(db_session, event_type="TEST_EVENT", actor=ActorType.SYSTEM,
                          reason="unit test event")
    assert event.id is not None
    assert event.event_type == "TEST_EVENT"


def test_get_trail_for_order_orders_by_timestamp(db_session):
    from app.models import Order, OrderStatus
    order = Order(user_id="user_test", status=OrderStatus.CART, total_amount=0)
    db_session.add(order)
    db_session.commit()
    record_event(db_session, event_type="A", order_id=order.id)
    record_event(db_session, event_type="B", order_id=order.id)
    trail = get_trail_for_order(db_session, order.id)
    assert [e.event_type for e in trail] == ["A", "B"]


def test_full_conversation_happy_path(db_session):
    sess = AgentSession(user_id="user_test", state={})
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)

    turn1 = agent.handle_turn(db_session, sess, "user_test", "I need black running shoes under 3000")
    assert turn1.messages
    assert turn1.messages[0].product_cards

    db_session.refresh(sess)
    turn2 = agent.handle_turn(db_session, sess, "user_test", "add it")
    assert "Added" in turn2.messages[0].text

    db_session.refresh(sess)
    turn3 = agent.handle_turn(db_session, sess, "user_test", "checkout")
    assert turn3.order_id is not None

    db_session.refresh(sess)
    turn4 = agent.handle_turn(db_session, sess, "user_test", "yes")
    assert turn4.messages[-1].ui_action == "LAUNCH_PAYMENT"


def test_over_budget_purchase_is_blocked_at_checkout(db_session):
    sess = AgentSession(user_id="user_test", state={})
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)

    agent.handle_turn(db_session, sess, "user_test", "show me a running watch")
    db_session.refresh(sess)
    agent.handle_turn(db_session, sess, "user_test", "add it")
    db_session.refresh(sess)
    result = agent.handle_turn(db_session, sess, "user_test", "checkout")
    assert result.messages[-1].policy_notice is not None
    assert result.messages[-1].policy_notice["allowed"] is False
