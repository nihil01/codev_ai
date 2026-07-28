alter table company_knowledge_base_entries
    add column if not exists quantity_available integer;

alter table company_knowledge_base_entries
    drop constraint if exists chk_company_knowledge_quantity_available;

alter table company_knowledge_base_entries
    add constraint chk_company_knowledge_quantity_available
        check (quantity_available is null or quantity_available >= 0);

create index if not exists ix_company_knowledge_quantity
    on company_knowledge_base_entries(company_id, quantity_available)
    where quantity_available is not null;
