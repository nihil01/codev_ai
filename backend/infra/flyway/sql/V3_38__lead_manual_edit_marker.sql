alter table crm_leads
    add column if not exists manually_updated_at timestamptz,
    add column if not exists manually_updated_by varchar(255);

create index if not exists ix_crm_leads_company_manual_update
    on crm_leads(company_id, manually_updated_at desc)
    where manually_updated_at is not null and is_deleted = false;
