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

create index if not exists ix_whatsapp_conversations_company_customer
    on whatsapp_conversations(company_id, customer_whatsapp_id);

create index if not exists ix_whatsapp_conversations_company_last_message
    on whatsapp_conversations(company_id, last_message_at desc nulls last, created_at desc);

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

create index if not exists ix_whatsapp_messages_conversation_created
    on whatsapp_messages(conversation_id, created_at desc);

create index if not exists ix_whatsapp_messages_company_created
    on whatsapp_messages(company_id, created_at desc);

do $$
begin
    if not exists (
        select 1 from pg_trigger where tgname = 'trg_whatsapp_conversations_updated_at'
    ) then
        create trigger trg_whatsapp_conversations_updated_at
        before update on whatsapp_conversations
        for each row execute function set_updated_at();
    end if;
end;
$$;
