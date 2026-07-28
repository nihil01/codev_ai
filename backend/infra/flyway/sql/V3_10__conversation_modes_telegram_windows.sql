-- Conversation control MVP: bot/human modes, 24h messaging window, Telegram manager notifications, audit.
-- Some integrator databases were created after WhatsApp Web.js was removed, so keep legacy
-- WhatsApp tables additive here instead of letting the migration fail on missing tables.

create table if not exists whatsapp_conversations (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    conversation_whatsapp_id varchar(255),
    customer_whatsapp_id varchar(255) not null,
    customer_phone varchar(64),
    customer_name varchar(255),
    last_message_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists ux_whatsapp_conversations_company_customer
    on whatsapp_conversations(company_id, customer_whatsapp_id);

create table if not exists whatsapp_messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references whatsapp_conversations(id) on delete cascade,
    company_id uuid not null references instagram_companies(id) on delete cascade,
    whatsapp_mid varchar(512),
    sender_whatsapp_id varchar(255) not null,
    recipient_whatsapp_id varchar(255) not null,
    direction varchar(16) not null,
    message_text text,
    message_type varchar(64),
    has_media boolean not null default false,
    message_payload jsonb,
    sent_at timestamptz,
    created_at timestamptz not null default now()
);

create unique index if not exists ux_whatsapp_messages_company_mid
    on whatsapp_messages(company_id, whatsapp_mid)
    where whatsapp_mid is not null;

alter table instagram_conversations
    add column if not exists mode varchar(16) not null default 'bot',
    add column if not exists assigned_manager_id uuid references users(id) on delete set null,
    add column if not exists bot_paused_at timestamptz,
    add column if not exists bot_paused_reason text,
    add column if not exists last_user_message_at timestamptz,
    add column if not exists messaging_window_expires_at timestamptz,
    add column if not exists last_manager_message_at timestamptz,
    add column if not exists last_bot_message_at timestamptz,
    add column if not exists status varchar(16) not null default 'open',
    add column if not exists priority varchar(16) not null default 'normal',
    add column if not exists version integer not null default 0;

alter table whatsapp_conversations
    add column if not exists mode varchar(16) not null default 'bot',
    add column if not exists assigned_manager_id uuid references users(id) on delete set null,
    add column if not exists bot_paused_at timestamptz,
    add column if not exists bot_paused_reason text,
    add column if not exists last_user_message_at timestamptz,
    add column if not exists messaging_window_expires_at timestamptz,
    add column if not exists last_manager_message_at timestamptz,
    add column if not exists last_bot_message_at timestamptz,
    add column if not exists status varchar(16) not null default 'open',
    add column if not exists priority varchar(16) not null default 'normal',
    add column if not exists version integer not null default 0;

alter table whatsapp_cloud_conversations
    add column if not exists mode varchar(16) not null default 'bot',
    add column if not exists assigned_manager_id uuid references users(id) on delete set null,
    add column if not exists bot_paused_at timestamptz,
    add column if not exists bot_paused_reason text,
    add column if not exists last_user_message_at timestamptz,
    add column if not exists messaging_window_expires_at timestamptz,
    add column if not exists last_manager_message_at timestamptz,
    add column if not exists last_bot_message_at timestamptz,
    add column if not exists status varchar(16) not null default 'open',
    add column if not exists priority varchar(16) not null default 'normal',
    add column if not exists version integer not null default 0;

alter table instagram_messages
    add column if not exists sender_type varchar(16),
    add column if not exists manager_id uuid references users(id) on delete set null,
    add column if not exists external_message_id text,
    add column if not exists intent varchar(64),
    add column if not exists intent_confidence numeric(5,4),
    add column if not exists delivery_status varchar(32) not null default 'sent',
    add column if not exists delivery_error text;

alter table whatsapp_messages
    add column if not exists sender_type varchar(16),
    add column if not exists manager_id uuid references users(id) on delete set null,
    add column if not exists external_message_id text,
    add column if not exists intent varchar(64),
    add column if not exists intent_confidence numeric(5,4),
    add column if not exists delivery_status varchar(32) not null default 'sent',
    add column if not exists delivery_error text;

alter table whatsapp_cloud_messages
    add column if not exists sender_type varchar(16),
    add column if not exists manager_id uuid references users(id) on delete set null,
    add column if not exists external_message_id text,
    add column if not exists intent varchar(64),
    add column if not exists intent_confidence numeric(5,4),
    add column if not exists delivery_status varchar(32) not null default 'sent',
    add column if not exists delivery_error text;

update instagram_messages set sender_type = case when direction = 'inbound' then 'customer' else 'bot' end where sender_type is null;
update whatsapp_messages set sender_type = case when direction = 'inbound' then 'customer' else 'bot' end where sender_type is null;
update whatsapp_cloud_messages set sender_type = case when direction = 'inbound' then 'customer' else 'bot' end where sender_type is null;
update instagram_messages set external_message_id = instagram_mid where external_message_id is null and instagram_mid is not null;
update whatsapp_messages set external_message_id = whatsapp_mid where external_message_id is null and whatsapp_mid is not null;
update whatsapp_cloud_messages set external_message_id = whatsapp_mid where external_message_id is null and whatsapp_mid is not null;

alter table instagram_messages alter column sender_type set default 'customer';
alter table whatsapp_messages alter column sender_type set default 'customer';
alter table whatsapp_cloud_messages alter column sender_type set default 'customer';

alter table users
    add column if not exists telegram_chat_id bigint,
    add column if not exists telegram_user_id bigint,
    add column if not exists telegram_username text,
    add column if not exists telegram_notifications_enabled boolean not null default false;

create table if not exists telegram_connect_tokens (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    token text not null unique,
    expires_at timestamptz not null,
    used_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists conversation_audit_log (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    channel varchar(32) not null,
    conversation_id uuid not null,
    actor_type varchar(32) not null,
    actor_id uuid,
    action varchar(64) not null,
    old_mode varchar(16),
    new_mode varchar(16),
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists telegram_notification_log (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    user_id uuid references users(id) on delete set null,
    channel varchar(32),
    conversation_id uuid,
    notification_type varchar(64) not null,
    message_text text not null,
    telegram_message_id text,
    status varchar(32) not null default 'pending',
    error_text text,
    created_at timestamptz not null default now(),
    sent_at timestamptz
);

create index if not exists ix_instagram_conversations_mode_window on instagram_conversations(company_id, mode, messaging_window_expires_at);
create index if not exists ix_whatsapp_conversations_mode_window on whatsapp_conversations(company_id, mode, messaging_window_expires_at);
create index if not exists ix_wp_cloud_conversations_mode_window on whatsapp_cloud_conversations(company_id, mode, messaging_window_expires_at);
create index if not exists ix_conversation_audit_log_conversation on conversation_audit_log(channel, conversation_id, created_at);
create index if not exists ix_telegram_connect_tokens_token on telegram_connect_tokens(token);
