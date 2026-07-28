alter table instagram_conversations
    add column if not exists zernio_conversation_id text;

alter table whatsapp_conversations
    add column if not exists zernio_conversation_id text,
    add column if not exists last_client_reminder_sent_at timestamptz;

create index if not exists ix_instagram_conversations_zernio_conversation
    on instagram_conversations(company_id, zernio_conversation_id)
    where zernio_conversation_id is not null;

create index if not exists ix_whatsapp_conversations_zernio_conversation
    on whatsapp_conversations(company_id, zernio_conversation_id)
    where zernio_conversation_id is not null;
