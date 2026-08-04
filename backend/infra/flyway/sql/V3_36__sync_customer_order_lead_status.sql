alter table customer_orders
    drop constraint if exists fk_customer_orders_crm_lead;

alter table customer_orders
    add constraint fk_customer_orders_crm_lead
    foreign key (company_id, lead_id)
    references crm_leads(company_id, id)
    on delete set null (lead_id);

alter table instagram_comments
    drop constraint if exists fk_instagram_comments_crm_lead;

alter table instagram_comments
    add constraint fk_instagram_comments_crm_lead
    foreign key (company_id, lead_id)
    references crm_leads(company_id, id)
    on delete set null (lead_id);

create or replace function sync_customer_order_lead_status()
returns trigger
language plpgsql
as $$
begin
    if new.lead_id is null then
        return new;
    end if;

    update crm_leads
    set status = case
            when new.status in ('paid', 'completed', 'done') then 'enrolled'
            when new.status = 'cancelled' then 'lost'
            when new.status = 'accepted' and status <> 'enrolled' then 'qualified'
            when new.status in ('new', 'sent_to_manager')
                 and status in ('new', 'interested', 'contacted') then 'interested'
            else status
        end,
        last_interaction_at = greatest(coalesce(last_interaction_at, new.updated_at), new.updated_at),
        updated_at = now()
    where id = new.lead_id
      and company_id = new.company_id;

    return new;
end;
$$;

drop trigger if exists trg_customer_orders_sync_lead_status on customer_orders;
create trigger trg_customer_orders_sync_lead_status
after insert or update of status, lead_id on customer_orders
for each row execute function sync_customer_order_lead_status();
