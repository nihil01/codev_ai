create table if not exists whatsapp_cloud_conversations (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    integration_id uuid not null references whatsapp_cloud_integrations(id) on delete cascade,
    phone_number_id text not null,
    waba_id text,
    customer_whatsapp_id text not null,
    customer_phone text,
    customer_name text,
    last_message_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_wp_cloud_company_integration_customer unique (company_id, integration_id, customer_whatsapp_id)
);

create index if not exists ix_wp_cloud_conversations_company_customer
    on whatsapp_cloud_conversations(company_id, customer_whatsapp_id);

create index if not exists ix_wp_cloud_conversations_integration_customer
    on whatsapp_cloud_conversations(integration_id, customer_whatsapp_id);

create index if not exists ix_wp_cloud_conversations_company_last_message
    on whatsapp_cloud_conversations(company_id, last_message_at desc nulls last, created_at desc);

create table if not exists whatsapp_cloud_messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references whatsapp_cloud_conversations(id) on delete cascade,
    company_id uuid not null references instagram_companies(id) on delete cascade,
    integration_id uuid not null references whatsapp_cloud_integrations(id) on delete cascade,
    whatsapp_mid text,
    sender_whatsapp_id text not null,
    recipient_whatsapp_id text not null,
    direction varchar(16) not null,
    message_text text,
    message_type varchar(64),
    has_media boolean not null default false,
    message_payload jsonb,
    sent_at timestamptz,
    created_at timestamptz not null default now()
);

create unique index if not exists ux_wp_cloud_messages_company_mid
    on whatsapp_cloud_messages(company_id, whatsapp_mid)
    where whatsapp_mid is not null;

create index if not exists ix_wp_cloud_messages_conversation_created
    on whatsapp_cloud_messages(conversation_id, created_at asc);

create index if not exists ix_wp_cloud_messages_company_created
    on whatsapp_cloud_messages(company_id, created_at desc);

create index if not exists ix_wp_cloud_messages_integration_created
    on whatsapp_cloud_messages(integration_id, created_at desc);

do $$
begin
    if not exists (
        select 1 from pg_trigger where tgname = 'trg_whatsapp_cloud_conversations_updated_at'
    ) then
        create trigger trg_whatsapp_cloud_conversations_updated_at
        before update on whatsapp_cloud_conversations
        for each row execute function set_updated_at();
    end if;
end;
$$;
