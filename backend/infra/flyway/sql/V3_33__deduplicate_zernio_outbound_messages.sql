-- Remove historical Zernio outbound duplicates created when the API send path
-- persisted message.id while the message.sent webhook persisted platformMessageId.
-- Matching by both IDs from the same webhook payload avoids deleting legitimate
-- repeated messages that merely have identical text.
WITH instagram_duplicate_ids AS (
    SELECT DISTINCT local_message.id
    FROM instagram_messages local_message
    JOIN instagram_messages webhook_message
      ON webhook_message.company_id = local_message.company_id
     AND webhook_message.conversation_id = local_message.conversation_id
     AND webhook_message.id <> local_message.id
    WHERE local_message.direction = 'outbound'
      AND webhook_message.direction = 'outbound'
      AND webhook_message.message_payload ->> 'event' = 'message.sent'
      AND local_message.instagram_mid = webhook_message.message_payload #>> '{message,id}'
      AND webhook_message.instagram_mid = COALESCE(
          webhook_message.message_payload #>> '{message,platformMessageId}',
          webhook_message.message_payload #>> '{message,platform_message_id}'
      )
),
deleted_instagram AS (
    DELETE FROM instagram_messages message
    USING instagram_duplicate_ids duplicate
    WHERE message.id = duplicate.id
    RETURNING message.company_id, message.created_at
),
whatsapp_duplicate_ids AS (
    SELECT DISTINCT local_message.id
    FROM whatsapp_messages local_message
    JOIN whatsapp_messages webhook_message
      ON webhook_message.company_id = local_message.company_id
     AND webhook_message.conversation_id = local_message.conversation_id
     AND webhook_message.id <> local_message.id
    WHERE local_message.direction = 'outbound'
      AND webhook_message.direction = 'outbound'
      AND webhook_message.message_payload ->> 'event' = 'message.sent'
      AND local_message.whatsapp_mid = webhook_message.message_payload #>> '{message,id}'
      AND webhook_message.whatsapp_mid = COALESCE(
          webhook_message.message_payload #>> '{message,platformMessageId}',
          webhook_message.message_payload #>> '{message,platform_message_id}'
      )
),
deleted_whatsapp AS (
    DELETE FROM whatsapp_messages message
    USING whatsapp_duplicate_ids duplicate
    WHERE message.id = duplicate.id
    RETURNING message.company_id, message.created_at
),
removed_usage AS (
    SELECT company_id, to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM') AS usage_period, count(*)::integer AS removed_count
    FROM (
        SELECT company_id, created_at FROM deleted_instagram
        UNION ALL
        SELECT company_id, created_at FROM deleted_whatsapp
    ) removed
    GROUP BY company_id, to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM')
)
UPDATE company_usage_counters counters
SET text_messages_used = greatest(0, counters.text_messages_used - removed_usage.removed_count),
    updated_at = now()
FROM removed_usage
WHERE counters.company_id = removed_usage.company_id
  AND counters.usage_period = removed_usage.usage_period;
