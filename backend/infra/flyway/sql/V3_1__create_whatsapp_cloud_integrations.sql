create extension if not exists pgcrypto;

create table if not exists whatsapp_cloud_integrations (
    id uuid primary key default gen_random_uuid(),
    meta_business_id text,
    waba_id text not null,
    phone_number_id text not null,
    access_token text not null,
    display_phone_number text,
    verified_name text,
    quality_rating text,
    webhook_subscribed boolean not null default false,
    connected_at timestamptz not null default now(),
    disconnected_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_whatsapp_cloud_integrations_phone_number_id unique (phone_number_id)
);

create index if not exists idx_whatsapp_cloud_integrations_waba_id
    on whatsapp_cloud_integrations(waba_id);

create index if not exists idx_whatsapp_cloud_integrations_phone_number_id
    on whatsapp_cloud_integrations(phone_number_id);

do $$
begin
    if exists (
        select 1
        from information_schema.columns
        where table_name = 'users'
          and column_name = 'company_id'
    ) and not exists (
        select 1
        from information_schema.columns
        where table_name = 'users'
          and column_name = 'instagram_company_id'
    ) then
        alter table users rename column company_id to instagram_company_id;
    end if;
end;
$$;

alter table users
    add column if not exists whatsapp_company_id uuid references whatsapp_cloud_integrations(id) on delete set null;

create index if not exists ix_users_instagram_company_id on users(instagram_company_id);
create index if not exists ix_users_whatsapp_company_id on users(whatsapp_company_id);
