create table if not exists company_intent_prompts (
    company_id uuid primary key references instagram_companies(id) on delete cascade,
    title varchar(255) not null default 'Söhbət intenti promptu',
    prompt_text text not null,
    version integer not null default 1 check (version > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create trigger trg_company_intent_prompts_updated_at
before update on company_intent_prompts
for each row execute function set_updated_at();
