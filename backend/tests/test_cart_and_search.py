from app.models import Cart, CartItem, ActorType
from app.services import cart_service, product_service


def test_search_products_filters_by_budget_and_color(db_session):
    results = product_service.search_products(db_session, query="running shoes", max_price=3000, color="black")
    assert results
    for p in results:
        assert p.price <= 3000
        assert "black" in p.color.lower()


def test_search_products_excludes_out_of_stock(db_session):
    product = product_service.get_product(db_session, "SHOE_101")
    product.stock = 0
    db_session.commit()
    results = product_service.search_products(db_session, query="running")
    assert all(p.id != "SHOE_101" for p in results)


def test_cart_totals_separate_upsell_amount(db_session):
    cart = Cart(user_id="user_test", session_id="sess_1")
    db_session.add(cart)
    db_session.commit()
    shoe = product_service.get_product(db_session, "SHOE_102")
    socks = product_service.get_product(db_session, "SOCK_201")
    cart_service.add_item(db_session, cart, shoe, quantity=1, added_by=ActorType.AGENT, is_upsell=False)
    cart_service.add_item(db_session, cart, socks, quantity=1, added_by=ActorType.AGENT, is_upsell=True)

    totals = cart_service.calculate_totals(cart)
    assert totals["subtotal"] == shoe.price + socks.price
    assert totals["upsell_amount"] == socks.price
    assert totals["total"] == shoe.price + socks.price


def test_add_item_increments_quantity_for_same_product(db_session):
    cart = Cart(user_id="user_test", session_id="sess_2")
    db_session.add(cart)
    db_session.commit()
    shoe = product_service.get_product(db_session, "SHOE_102")
    cart_service.add_item(db_session, cart, shoe, quantity=1)
    item = cart_service.add_item(db_session, cart, shoe, quantity=1)
    assert item.quantity == 2
