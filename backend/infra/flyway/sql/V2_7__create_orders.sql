create table if not exists customer_orders (
    id uuid primary key,

    company_id uuid not null references instagram_companies(id) on delete cascade,

    channel varchar(32) not null,
    customer_id text not null,

    conversation_id uuid null,
    source_message_id text null,

    customer_name text null,
    customer_phone text null,

    product_title text null,
    product_price text null,
    quantity integer null,

    delivery_required boolean null,
    delivery_address text null,
    delivery_time text null,

    customer_comment text null,

    raw_summary text not null,
    raw_intent_payload jsonb not null default '{}'::jsonb,

    status varchar(32) not null default 'new',

    manager_notified_at timestamptz null,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint customer_orders_channel_check
        check (channel in ('whatsapp', 'instagram', 'manual')),

    constraint customer_orders_status_check
        check (status in ('new', 'sent_to_manager', 'accepted', 'cancelled', 'done')),

    constraint customer_orders_quantity_check
        check (quantity is null or quantity > 0)
);

create unique index if not exists ux_customer_orders_company_channel_source_message
    on customer_orders(company_id, channel, source_message_id);

create index if not exists ix_customer_orders_company_status
    on customer_orders(company_id, status);

create index if not exists ix_customer_orders_company_created_at
    on customer_orders(company_id, created_at desc);

create index if not exists ix_customer_orders_customer_id
    on customer_orders(customer_id);