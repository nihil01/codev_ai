create table if not exists telegram_manager_registration_tokens (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    created_by_user_id uuid references users(id) on delete set null,
    token text not null unique,
    expires_at timestamptz not null,
    used_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists telegram_company_managers (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    telegram_user_id bigint not null,
    telegram_chat_id bigint not null,
    telegram_username text,
    first_name text,
    last_name text,
    display_name text not null,
    language_code text,
    is_active boolean not null default true,
    registered_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint ux_telegram_company_managers_company_user unique (company_id, telegram_user_id)
);

create index if not exists ix_telegram_manager_registration_tokens_token
    on telegram_manager_registration_tokens(token);

create index if not exists ix_telegram_manager_registration_tokens_company
    on telegram_manager_registration_tokens(company_id, expires_at);

create index if not exists ix_telegram_company_managers_company_active
    on telegram_company_managers(company_id, is_active, display_name);

create index if not exists ix_telegram_company_managers_user
    on telegram_company_managers(telegram_user_id);
