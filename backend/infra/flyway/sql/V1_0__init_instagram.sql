create extension if not exists pgcrypto;

create table instagram_companies (
    id uuid primary key default gen_random_uuid(),
    instagram_account_id varchar(64) not null unique,
    username varchar(255),
    display_name varchar(255),
    app_scoped_user_id varchar(128),
    status varchar(32) not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    deauthorized_at timestamptz,
    deleted_at timestamptz
);

create table instagram_tokens (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    token_kind varchar(32) not null default 'long_lived',
    access_token text not null,
    permissions jsonb not null default '[]'::jsonb,
    issued_at timestamptz not null default now(),
    expires_at timestamptz,
    refresh_after timestamptz,
    last_refreshed_at timestamptz,
    last_validated_at timestamptz,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index ux_instagram_tokens_company_active
    on instagram_tokens(company_id)
    where is_active = true;

create index ix_instagram_tokens_refresh_after
    on instagram_tokens(refresh_after)
    where is_active = true;

create index ix_instagram_tokens_expires_at
    on instagram_tokens(expires_at)
    where is_active = true;

create table instagram_token_refresh_logs (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    old_token_id uuid references instagram_tokens(id) on delete set null,
    new_token_id uuid references instagram_tokens(id) on delete set null,
    operation varchar(32) not null, -- exchange_short_to_long | refresh
    status varchar(32) not null,    -- success | failed
    response_status_code integer,
    response_body text,
    error_message text,
    created_at timestamptz not null default now()
);

create table instagram_system_prompts (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    title varchar(255) not null default 'Default prompt',
    prompt_text text not null,
    is_active boolean not null default true,
    version integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index ux_instagram_system_prompts_active
    on instagram_system_prompts(company_id)
    where is_active = true;

create table instagram_conversations (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    conversation_instagram_id varchar(128),
    customer_instagram_id varchar(128) not null,
    customer_username varchar(255),
    last_message_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(company_id, customer_instagram_id)
);

create index ix_instagram_conversations_company_customer
    on instagram_conversations(company_id, customer_instagram_id);

create table instagram_messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references instagram_conversations(id) on delete cascade,
    company_id uuid not null references instagram_companies(id) on delete cascade,
    instagram_mid varchar(512),
    sender_instagram_id varchar(128) not null,
    recipient_instagram_id varchar(128) not null,
    direction varchar(16) not null, -- inbound | outbound
    message_text text,
    message_payload jsonb,
    sent_at timestamptz,
    created_at timestamptz not null default now(),
    unique(company_id, instagram_mid)
);

create index ix_instagram_messages_conversation_created
    on instagram_messages(conversation_id, created_at desc);

create table instagram_webhook_events (
    id uuid primary key default gen_random_uuid(),
    company_id uuid references instagram_companies(id) on delete cascade,
    instagram_mid varchar(512) not null,
    sender_instagram_id varchar(128),
    recipient_instagram_id varchar(128),
    event_type varchar(64) not null default 'message',
    payload jsonb not null,
    processed boolean not null default false,
    created_at timestamptz not null default now(),
    processed_at timestamptz,
    unique(instagram_mid)
);

create index ix_instagram_webhook_events_processed
    on instagram_webhook_events(processed, created_at);

create table instagram_data_deletion_requests (
    id uuid primary key default gen_random_uuid(),
    company_id uuid references instagram_companies(id) on delete set null,
    confirmation_code uuid not null unique,
    request_payload jsonb,
    status varchar(32) not null default 'completed',
    created_at timestamptz not null default now()
);

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger trg_instagram_companies_updated_at
before update on instagram_companies
for each row execute function set_updated_at();

create trigger trg_instagram_tokens_updated_at
before update on instagram_tokens
for each row execute function set_updated_at();

create trigger trg_instagram_system_prompts_updated_at
before update on instagram_system_prompts
for each row execute function set_updated_at();

create trigger trg_instagram_conversations_updated_at
before update on instagram_conversations
for each row execute function set_updated_at();
