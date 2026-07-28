create table if not exists company_knowledge_base_entries (
    id uuid primary key,
    company_id uuid not null references instagram_companies(id) on delete cascade,
    entry_type varchar(32) not null default 'text',
    title varchar(255) not null,
    content text not null,
    source_url text,
    image_url text,
    image_mime_type varchar(128),
    ai_generated_description text,
    is_active boolean not null default true,
    created_at timestamptz not null,
    updated_at timestamptz not null
);

create index if not exists idx_kb_entries_company_active
    on company_knowledge_base_entries(company_id, is_active, updated_at desc);

create index if not exists idx_kb_entries_company_text
    on company_knowledge_base_entries using gin (
        to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, '') || ' ' || coalesce(ai_generated_description, ''))
    );
