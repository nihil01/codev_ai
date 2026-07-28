create table if not exists zernio_tiktok_connected_accounts (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    zernio_profile_id text not null,
    zernio_account_id text not null,
    tiktok_account_id text,
    username text,
    display_name text,
    account_payload jsonb not null default '{}'::jsonb,
    last_seen_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_zernio_tiktok_connected_accounts_company_account unique (company_id, zernio_account_id),
    constraint uq_zernio_tiktok_connected_accounts_account unique (zernio_account_id)
);

create unique index if not exists ux_zernio_tiktok_connected_accounts_tiktok_account
    on zernio_tiktok_connected_accounts(tiktok_account_id)
    where tiktok_account_id is not null;

create index if not exists ix_zernio_tiktok_connected_accounts_company_id
    on zernio_tiktok_connected_accounts(company_id);

create index if not exists ix_zernio_tiktok_connected_accounts_profile_id
    on zernio_tiktok_connected_accounts(zernio_profile_id);

alter table social_posting_connections
    drop constraint if exists chk_social_posting_connections_platform;

alter table social_posting_connections
    add constraint chk_social_posting_connections_platform check (platform in ('instagram', 'linkedin', 'tiktok'));

alter table social_post_drafts
    add column if not exists zernio_post_id text,
    add column if not exists published_at timestamptz,
    add column if not exists last_attempt_at timestamptz,
    add column if not exists error_message text,
    add column if not exists metadata jsonb not null default '{}'::jsonb;

create index if not exists ix_social_post_drafts_company_platform_status
    on social_post_drafts(company_id, platform, status, scheduled_for);

create index if not exists ix_social_post_drafts_zernio_post_id
    on social_post_drafts(zernio_post_id)
    where zernio_post_id is not null;

do $$
begin
    if not exists (
        select 1 from pg_trigger where tgname = 'trg_zernio_tiktok_connected_accounts_updated_at'
    ) then
        create trigger trg_zernio_tiktok_connected_accounts_updated_at
        before update on zernio_tiktok_connected_accounts
        for each row execute function set_updated_at();
    end if;
end;
$$;
