create table if not exists instagram_comment_prompts (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    title varchar(255) not null default 'Instagram comment prompt',
    prompt_text text not null,
    is_active boolean not null default true,
    version integer not null default 1,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists ux_instagram_comment_prompts_active
    on instagram_comment_prompts(company_id)
    where is_active;

create table if not exists instagram_comment_threads (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    zernio_account_id text not null,
    platform_post_id text not null,
    zernio_post_id text,
    post_permalink text,
    post_caption text,
    comment_count integer not null default 0,
    inbound_comment_count integer not null default 0,
    replied_comment_count integer not null default 0,
    converted_comment_count integer not null default 0,
    last_comment_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (company_id, platform_post_id)
);

create index if not exists ix_instagram_comment_threads_company_updated
    on instagram_comment_threads(company_id, updated_at desc);

create table if not exists instagram_comments (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    thread_id uuid not null references instagram_comment_threads(id) on delete cascade,
    zernio_event_id uuid references zernio_webhook_events(id) on delete set null,
    zernio_account_id text not null,
    zernio_profile_id text,
    platform_comment_id text not null,
    platform_post_id text not null,
    zernio_post_id text,
    parent_comment_id text,
    author_id text not null,
    author_username text,
    author_name text,
    author_picture text,
    text_message text not null default '',
    direction varchar(16) not null default 'inbound',
    is_reply boolean not null default false,
    is_ad_comment boolean not null default false,
    ad_id text,
    ad_title text,
    status varchar(32) not null default 'new',
    ai_suggested_reply text,
    ai_generated_at timestamptz,
    replied_at timestamptz,
    converted_at timestamptz,
    raw_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null,
    inserted_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (company_id, platform_comment_id),
    constraint chk_instagram_comments_direction check (direction in ('inbound', 'outbound')),
    constraint chk_instagram_comments_status check (status in ('new', 'suggested', 'replied', 'ignored', 'converted'))
);

create index if not exists ix_instagram_comments_company_created
    on instagram_comments(company_id, created_at desc);

create index if not exists ix_instagram_comments_thread_created
    on instagram_comments(thread_id, created_at desc);

create index if not exists ix_instagram_comments_author
    on instagram_comments(company_id, author_id);
