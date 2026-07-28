create table if not exists company_managers (
    id uuid primary key,
    company_id uuid not null references instagram_companies(id) on delete cascade,
    channel varchar(32) not null,
    recipient_id text not null,
    display_name text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint company_managers_channel_check
        check (channel in ('instagram', 'whatsapp')),

    constraint ux_company_managers_company_channel_recipient
        unique (company_id, channel, recipient_id)
);

create index if not exists ix_company_managers_company_channel
    on company_managers(company_id, channel);

create table if not exists order_manager_notifications (
    id uuid primary key,
    order_id uuid not null references customer_orders(id) on delete cascade,
    manager_id uuid null references company_managers(id) on delete set null,
    company_id uuid not null references instagram_companies(id) on delete cascade,
    channel varchar(32) not null,
    recipient_id text not null,
    message_text text not null,
    status varchar(32) not null default 'pending',
    external_message_id text null,
    error_text text null,
    created_at timestamptz not null default now(),
    sent_at timestamptz null,

    constraint order_manager_notifications_channel_check
        check (channel in ('instagram', 'whatsapp')),

    constraint order_manager_notifications_status_check
        check (status in ('pending', 'sent', 'failed'))
);

create index if not exists ix_order_manager_notifications_order
    on order_manager_notifications(order_id);

create table if not exists broadcast_campaigns (
    id uuid primary key,
    company_id uuid not null references instagram_companies(id) on delete cascade,
    target varchar(32) not null,
    message_text text not null,
    status varchar(32) not null default 'pending',
    requested_count integer not null default 0,
    sent_count integer not null default 0,
    failed_count integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz null,

    constraint broadcast_campaigns_target_check
        check (target in ('instagram', 'whatsapp', 'both')),

    constraint broadcast_campaigns_status_check
        check (status in ('pending', 'running', 'completed', 'failed', 'partial'))
);

create index if not exists ix_broadcast_campaigns_company_created_at
    on broadcast_campaigns(company_id, created_at desc);

create table if not exists broadcast_recipients (
    id uuid primary key,
    campaign_id uuid not null references broadcast_campaigns(id) on delete cascade,
    company_id uuid not null references instagram_companies(id) on delete cascade,
    channel varchar(32) not null,
    recipient_id text not null,
    conversation_id uuid null,
    status varchar(32) not null default 'pending',
    external_message_id text null,
    error_text text null,
    created_at timestamptz not null default now(),
    sent_at timestamptz null,

    constraint broadcast_recipients_channel_check
        check (channel in ('instagram', 'whatsapp')),

    constraint broadcast_recipients_status_check
        check (status in ('pending', 'sent', 'failed')),

    constraint ux_broadcast_recipients_campaign_channel_recipient
        unique (campaign_id, channel, recipient_id)
);

create index if not exists ix_broadcast_recipients_campaign
    on broadcast_recipients(campaign_id);

create index if not exists ix_broadcast_recipients_company_channel
    on broadcast_recipients(company_id, channel);
