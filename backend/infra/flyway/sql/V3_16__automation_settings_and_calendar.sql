create table if not exists company_automation_settings (
    company_id uuid primary key references instagram_companies(id) on delete cascade,
    client_reminder_enabled boolean not null default false,
    client_reminder_delay_minutes integer not null default 120,
    client_reminder_message text not null default 'Здравствуйте! Хотели мягко напомнить о нашем диалоге. Если вопрос ещё актуален — напишите, мы рядом и поможем.',
    autoposting_enabled boolean not null default false,
    linkedin_connected boolean not null default false,
    tiktok_connected boolean not null default false,
    content_calendar_enabled boolean not null default false,
    flower_price_adaptation_enabled boolean not null default false,
    default_event_reminder_hours integer not null default 24,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_company_automation_reminder_delay check (client_reminder_delay_minutes between 15 and 1440),
    constraint chk_company_automation_reminder_hours check (default_event_reminder_hours between 1 and 2160)
);

create table if not exists social_posting_connections (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    platform varchar(32) not null,
    status varchar(32) not null default 'planned',
    external_account_id text,
    display_name text,
    metadata jsonb not null default '{}'::jsonb,
    connected_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_social_posting_connections_platform check (platform in ('linkedin', 'tiktok')),
    constraint chk_social_posting_connections_status check (status in ('planned', 'connected', 'disabled', 'error'))
);

create unique index if not exists ux_social_posting_connections_company_platform
    on social_posting_connections(company_id, platform);

create table if not exists social_post_drafts (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    platform varchar(32) not null,
    title text,
    caption text not null,
    media_urls jsonb not null default '[]'::jsonb,
    scheduled_for timestamptz,
    status varchar(32) not null default 'draft',
    publish_result jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_social_post_drafts_platform check (platform in ('instagram', 'whatsapp', 'linkedin', 'tiktok')),
    constraint chk_social_post_drafts_status check (status in ('draft', 'scheduled', 'publishing', 'published', 'failed', 'cancelled'))
);

create index if not exists ix_social_post_drafts_company_status_schedule
    on social_post_drafts(company_id, status, scheduled_for);

create table if not exists company_calendar_events (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    title text not null,
    description text,
    event_type varchar(32) not null default 'order',
    event_at timestamptz not null,
    customer_id text,
    order_id uuid references customer_orders(id) on delete set null,
    flower_type text,
    base_price numeric(12,2),
    adjusted_price numeric(12,2),
    price_strategy jsonb not null default '{}'::jsonb,
    reminder_sent_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_company_calendar_events_type check (event_type in ('order', 'campaign', 'custom', 'flower_supply')),
    constraint chk_company_calendar_prices check (
        (base_price is null or base_price >= 0) and (adjusted_price is null or adjusted_price >= 0)
    )
);

create index if not exists ix_company_calendar_events_company_event_at
    on company_calendar_events(company_id, event_at);

alter table instagram_conversations
    add column if not exists last_client_reminder_sent_at timestamptz;

alter table whatsapp_cloud_conversations
    add column if not exists last_client_reminder_sent_at timestamptz;

do $$
begin
    if not exists (
        select 1 from pg_trigger where tgname = 'trg_company_automation_settings_updated_at'
    ) then
        create trigger trg_company_automation_settings_updated_at
        before update on company_automation_settings
        for each row execute function set_updated_at();
    end if;

    if not exists (
        select 1 from pg_trigger where tgname = 'trg_social_posting_connections_updated_at'
    ) then
        create trigger trg_social_posting_connections_updated_at
        before update on social_posting_connections
        for each row execute function set_updated_at();
    end if;

    if not exists (
        select 1 from pg_trigger where tgname = 'trg_social_post_drafts_updated_at'
    ) then
        create trigger trg_social_post_drafts_updated_at
        before update on social_post_drafts
        for each row execute function set_updated_at();
    end if;

    if not exists (
        select 1 from pg_trigger where tgname = 'trg_company_calendar_events_updated_at'
    ) then
        create trigger trg_company_calendar_events_updated_at
        before update on company_calendar_events
        for each row execute function set_updated_at();
    end if;
end;
$$;
