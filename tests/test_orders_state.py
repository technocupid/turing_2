import pytest
from app.core.state_machine import InvalidTransition
from app.models.order import Order, OrderItem

def test_order_state_transitions_and_history():
    o = Order(user_id="u1", items=[OrderItem(product_id="p1", unit_price=10.0, quantity=1)])
    assert o.status == "placed"
    o.transition_to("paid")
    assert o.status == "paid"
    o.transition_to("shipped")
    assert o.status == "shipped"
    o.transition_to("delivered")
    assert o.status == "delivered"
    assert len(o.status_history) == 3
    with pytest.raises(InvalidTransition):
        o.transition_to("paid")  # cannot go back