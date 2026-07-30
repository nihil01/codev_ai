from datetime import timedelta

from services.conversation_control import format_window_left, utcnow
from services.customer_orders import build_order_summary
from services.manager_notifications import build_manager_order_message


def test_manager_message_describes_course_lead_without_shop_fields():
    message = build_manager_order_message(
        {
            "channel": "whatsapp",
            "customer_id": "994501234567",
            "customer_name": "Orik",
            "customer_phone": "+994****4567",
            "product_title": "Python Backend",
            "product_price": "120 AZN",
            "quantity": 2,
            "delivery_required": True,
            "delivery_address": "Baku",
            "delivery_time": "today",
            "customer_comment": "Axşam qrupu ilə maraqlanır",
        }
    )

    assert "Yeni kurs müraciəti" in message
    assert "Müştəri: Orik" in message
    assert "Maraqlandığı kurs: Python Backend" in message
    assert "Kursun qiyməti: 120 AZN" in message
    assert "Qeyd: Axşam qrupu ilə maraqlanır" in message
    assert "Quantity" not in message
    assert "Delivery" not in message
    assert "Address" not in message


def test_stored_summary_describes_course_without_commerce_fields():
    summary = build_order_summary(
        channel="instagram",
        customer_id="customer-1",
        customer_name="Aysel",
        customer_phone=None,
        product_title="Frontend",
        product_price="150 AZN",
        quantity=10,
        delivery_required=True,
        delivery_address="Baku",
        delivery_time="today",
        customer_comment="Onlayn format",
    )

    assert "New course inquiry" in summary
    assert "Course: Frontend" in summary
    assert "Course price: 150 AZN" in summary
    assert "Quantity" not in summary
    assert "Delivery" not in summary


def test_manager_notification_window_format_is_english():
    assert format_window_left(utcnow() - timedelta(minutes=1)) == "closed"
    assert "h" in format_window_left(utcnow() + timedelta(hours=1, minutes=2))
