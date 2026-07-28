create table if not exists company_subscriptions (
    company_id uuid primary key references instagram_companies(id) on delete cascade,
    package_code varchar(32) not null default 'basic',
    monthly_text_messages_limit integer,
    monthly_voice_messages_limit integer,
    monthly_ai_videos_limit integer,
    autoposting_enabled boolean not null default false,
    access_locked boolean not null default false,
    locked_reason text,
    locked_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_company_subscriptions_package check (package_code in ('basic', 'full')),
    constraint chk_company_subscriptions_limits check (
        (monthly_text_messages_limit is null or monthly_text_messages_limit >= 0)
        and (monthly_voice_messages_limit is null or monthly_voice_messages_limit >= 0)
        and (monthly_ai_videos_limit is null or monthly_ai_videos_limit >= 0)
    )
);

create table if not exists company_usage_counters (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    usage_period varchar(7) not null,
    text_messages_used integer not null default 0,
    voice_messages_used integer not null default 0,
    ai_videos_used integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(company_id, usage_period),
    constraint chk_company_usage_period check (usage_period ~ '^\d{4}-\d{2}$'),
    constraint chk_company_usage_non_negative check (
        text_messages_used >= 0 and voice_messages_used >= 0 and ai_videos_used >= 0
    )
);

create index if not exists ix_company_usage_counters_company_period
    on company_usage_counters(company_id, usage_period desc);

insert into company_subscriptions (
    company_id, package_code, monthly_text_messages_limit,
    monthly_voice_messages_limit, monthly_ai_videos_limit,
    autoposting_enabled, access_locked, created_at, updated_at
)
select
    id,
    'basic',
    4000,
    1000,
    0,
    false,
    false,
    now(),
    now()
from instagram_companies
on conflict (company_id) do nothing;
