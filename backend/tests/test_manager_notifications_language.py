from datetime import timedelta

from services.conversation_control import format_window_left, utcnow
from services.manager_notifications import build_manager_order_message


def test_manager_order_message_is_english():
    message = build_manager_order_message(
        {
            "channel": "whatsapp",
            "customer_id": "994501234567",
            "customer_name": "Orik",
            "customer_phone": "+994501234567",
            "product_title": "Cake",
            "product_price": "45 AZN",
            "quantity": 2,
            "delivery_required": True,
            "delivery_address": "Baku",
            "delivery_time": "today",
            "customer_comment": "please call",
        }
    )

    assert "New order" in message
    assert "Customer name: Orik" in message
    assert "Delivery: yes" in message
    assert "Новый" not in message
    assert "Клиент" not in message


def test_manager_notification_window_format_is_english():
    assert format_window_left(utcnow() - timedelta(minutes=1)) == "closed"
    assert "h" in format_window_left(utcnow() + timedelta(hours=1, minutes=2))
