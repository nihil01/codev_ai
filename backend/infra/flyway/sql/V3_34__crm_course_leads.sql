create table if not exists crm_leads (
    id uuid primary key default gen_random_uuid(),
    company_id uuid not null references instagram_companies(id) on delete cascade,
    platform varchar(32) not null,
    external_id text not null,
    conversation_id uuid null,
    first_name varchar(255),
    last_name varchar(255),
    username varchar(255),
    phone varchar(64),
    email varchar(255),
    profile_link text,
    interested_in text,
    status varchar(32) not null default 'new',
    lead_source varchar(64) not null,
    first_interaction_at timestamptz,
    last_interaction_at timestamptz,
    ai_summary text,
    tags text[] not null default '{}'::text[],
    notes text,
    assigned_to varchar(255),
    next_follow_up_at timestamptz,
    source_comment_id uuid references instagram_comments(id) on delete set null,
    metadata jsonb not null default '{}'::jsonb,
    is_deleted boolean not null default false,
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint crm_leads_platform_check check (platform in ('instagram', 'facebook', 'tiktok', 'whatsapp')),
    constraint crm_leads_status_check check (status in ('new', 'interested', 'contacted', 'qualified', 'enrolled', 'not_interested', 'lost', 'archived')),
    constraint crm_leads_company_platform_external_unique unique (company_id, platform, external_id)
);

create index if not exists ix_crm_leads_company_status
    on crm_leads(company_id, status) where is_deleted = false;
create index if not exists ix_crm_leads_company_platform
    on crm_leads(company_id, platform) where is_deleted = false;
create index if not exists ix_crm_leads_company_last_interaction
    on crm_leads(company_id, last_interaction_at desc nulls last) where is_deleted = false;
create index if not exists ix_crm_leads_company_follow_up
    on crm_leads(company_id, next_follow_up_at) where next_follow_up_at is not null and is_deleted = false;
create index if not exists ix_crm_leads_company_interested
    on crm_leads(company_id, interested_in) where is_deleted = false;

create trigger trg_crm_leads_updated_at
before update on crm_leads
for each row execute function set_updated_at();

insert into crm_leads (
    company_id, platform, external_id, conversation_id, username, profile_link,
    lead_source, first_interaction_at, last_interaction_at
)
select
    company_id, 'instagram', customer_instagram_id::text, id, customer_username,
    case when customer_username is not null then 'https://www.instagram.com/' || customer_username else null end,
    'instagram_dm', created_at, last_message_at
from instagram_conversations
on conflict (company_id, platform, external_id) do nothing;

insert into crm_leads (
    company_id, platform, external_id, conversation_id, first_name, phone,
    lead_source, first_interaction_at, last_interaction_at
)
select
    company_id, 'whatsapp', customer_whatsapp_id::text, id, customer_name, customer_phone,
    'whatsapp', created_at, last_message_at
from whatsapp_cloud_conversations
on conflict (company_id, platform, external_id) do update set
    conversation_id = coalesce(crm_leads.conversation_id, excluded.conversation_id),
    first_name = coalesce(crm_leads.first_name, excluded.first_name),
    phone = coalesce(crm_leads.phone, excluded.phone),
    last_interaction_at = case
        when crm_leads.last_interaction_at is null then excluded.last_interaction_at
        when excluded.last_interaction_at is null then crm_leads.last_interaction_at
        else greatest(crm_leads.last_interaction_at, excluded.last_interaction_at)
    end;

insert into crm_leads (
    company_id, platform, external_id, conversation_id, first_name, phone,
    lead_source, first_interaction_at, last_interaction_at
)
select
    company_id, 'whatsapp', customer_whatsapp_id::text, id, customer_name, customer_phone,
    'whatsapp', created_at, last_message_at
from whatsapp_conversations
on conflict (company_id, platform, external_id) do update set
    conversation_id = coalesce(crm_leads.conversation_id, excluded.conversation_id),
    first_name = coalesce(crm_leads.first_name, excluded.first_name),
    phone = coalesce(crm_leads.phone, excluded.phone),
    last_interaction_at = case
        when crm_leads.last_interaction_at is null then excluded.last_interaction_at
        when excluded.last_interaction_at is null then crm_leads.last_interaction_at
        else greatest(crm_leads.last_interaction_at, excluded.last_interaction_at)
    end;
