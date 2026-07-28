-- Add business verticals, perishable inventory discounts, custom visual requests, and analytics-ready commercial fields.

create table if not exists company_business_settings (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    business_type varchar(32) not null default 'other',
    features jsonb not null default '{}'::jsonb,
    default_shelf_life_hours integer,
    default_discount_after_hours integer,
    default_discount_percent numeric(5,2) not null default 0,
    auto_discount_enabled boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_company_business_settings_type check (business_type in ('confectionery', 'flower_shop', 'cafe_restaurant', 'other')),
    constraint chk_company_business_settings_discount check (default_discount_percent >= 0 and default_discount_percent <= 100),
    constraint chk_company_business_settings_hours check (
        default_shelf_life_hours is null or default_shelf_life_hours > 0
    ),
    constraint chk_company_business_settings_discount_after check (
        default_discount_after_hours is null or default_discount_after_hours >= 0
    )
);

create unique index if not exists ux_company_business_settings_company
    on company_business_settings(company_id);
create index if not exists ix_company_business_settings_business_type
    on company_business_settings(business_type);

insert into company_business_settings (company_id, business_type, features)
select id, 'other', '{}'::jsonb
from instagram_companies
on conflict (company_id) do nothing;

create table if not exists product_inventory_items (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    title text not null,
    category text,
    quantity integer not null default 1,
    unit_cost numeric(12,2) not null default 0,
    original_price numeric(12,2) not null default 0,
    effective_price numeric(12,2) not null default 0,
    discount_percent numeric(5,2) not null default 0,
    shelf_life_hours integer,
    discount_after_hours integer,
    received_at timestamptz not null default now(),
    status varchar(32) not null default 'fresh',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_product_inventory_quantity check (quantity >= 0),
    constraint chk_product_inventory_prices check (unit_cost >= 0 and original_price >= 0 and effective_price >= 0),
    constraint chk_product_inventory_discount check (discount_percent >= 0 and discount_percent <= 100),
    constraint chk_product_inventory_status check (status in ('fresh', 'discounted', 'expired', 'sold', 'archived'))
);

create index if not exists ix_product_inventory_items_company_status
    on product_inventory_items(company_id, status);
create index if not exists ix_product_inventory_items_company_received
    on product_inventory_items(company_id, received_at);

create table if not exists custom_product_requests (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    business_type varchar(32) not null,
    customer_id text,
    channel varchar(32),
    title text not null,
    description text not null,
    budget text,
    generated_prompt text not null,
    generated_image_url text,
    status varchar(32) not null default 'draft',
    request_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_custom_product_requests_business_type check (business_type in ('confectionery', 'flower_shop', 'cafe_restaurant', 'other')),
    constraint chk_custom_product_requests_status check (status in ('draft', 'preview_ready', 'sent_to_customer', 'approved', 'rejected', 'cancelled'))
);

create index if not exists ix_custom_product_requests_company_status
    on custom_product_requests(company_id, status);
create index if not exists ix_custom_product_requests_customer
    on custom_product_requests(company_id, customer_id);

alter table customer_orders
    add column if not exists revenue_amount numeric(12,2),
    add column if not exists cost_amount numeric(12,2),
    add column if not exists paid_at timestamptz,
    add column if not exists completed_at timestamptz;

create index if not exists ix_customer_orders_company_completed_at
    on customer_orders(company_id, completed_at);
