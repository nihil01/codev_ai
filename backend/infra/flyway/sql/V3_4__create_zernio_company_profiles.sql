create table if not exists zernio_company_profiles (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    user_id uuid references users(id) on delete set null,
    zernio_profile_id text not null,
    profile_name text,
    company_email text not null,
    company_profile jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_zernio_company_profiles_company unique (company_id),
    constraint uq_zernio_company_profiles_profile unique (zernio_profile_id)
);

create index if not exists ix_zernio_company_profiles_user_id
    on zernio_company_profiles(user_id);

create index if not exists ix_zernio_company_profiles_company_email
    on zernio_company_profiles(company_email);
