create table if not exists zernio_webhook_events (
    id uuid primary key default gen_random_uuid(),
    company_id uuid references instagram_companies(id) on delete set null,
    zernio_profile_id text,
    zernio_account_id text,
    platform text,
    event_type text,
    payload jsonb not null default '{}'::jsonb,
    headers jsonb not null default '{}'::jsonb,
    processed boolean not null default false,
    received_at timestamptz not null default now(),
    processed_at timestamptz
);

create index if not exists ix_zernio_webhook_events_company_id
    on zernio_webhook_events(company_id);

create index if not exists ix_zernio_webhook_events_zernio_account_id
    on zernio_webhook_events(zernio_account_id);

create index if not exists ix_zernio_webhook_events_zernio_profile_id
    on zernio_webhook_events(zernio_profile_id);

create index if not exists ix_zernio_webhook_events_received_at
    on zernio_webhook_events(received_at);
