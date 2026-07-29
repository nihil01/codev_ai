from services.message_activity import MESSAGE_EVENTS_CTE


def test_message_activity_reads_every_supported_message_source() -> None:
    normalized = " ".join(MESSAGE_EVENTS_CTE.split()).lower()

    assert "from instagram_messages" in normalized
    assert "from whatsapp_cloud_messages" in normalized
    assert "from whatsapp_messages" in normalized
    assert normalized.count("where m.company_id = :company_id") == 3
    assert normalized.count("c.company_id = m.company_id") == 3
    assert normalized.count("c.company_id = :company_id") == 3
    assert "asia/baku" in normalized


def test_customer_rankings_are_limited_independently() -> None:
    import inspect
    from services.message_activity import load_message_activity

    normalized = " ".join(inspect.getsource(load_message_activity).split()).lower()
    assert "top_period as" in normalized
    assert "top_today as" in normalized
    assert normalized.count("limit 8") == 2
    assert "limit 100" not in normalized
