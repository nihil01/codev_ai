create table if not exists zernio_instagram_connected_accounts (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    zernio_profile_id text not null,
    zernio_account_id text not null,
    instagram_account_id text,
    username text,
    display_name text,
    account_payload jsonb not null default '{}'::jsonb,
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_zernio_instagram_connected_accounts_company_account unique (company_id, zernio_account_id)
);

create index if not exists ix_zernio_instagram_connected_accounts_company_id
    on zernio_instagram_connected_accounts(company_id);

create index if not exists ix_zernio_instagram_connected_accounts_profile_id
    on zernio_instagram_connected_accounts(zernio_profile_id);

create index if not exists ix_zernio_instagram_connected_accounts_instagram_account_id
    on zernio_instagram_connected_accounts(instagram_account_id);
