create table users (
    id uuid primary key default gen_random_uuid(),
    email varchar(255) not null unique,
    password_hash varchar(255) not null,
    role varchar(32) not null default 'admin',
    company_id uuid references instagram_companies(id) on delete cascade,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index ix_users_email on users(email);
create index ix_users_company_id on users(company_id);
