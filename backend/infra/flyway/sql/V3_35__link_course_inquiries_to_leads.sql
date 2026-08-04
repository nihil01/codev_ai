alter table crm_leads
    add constraint uq_crm_leads_company_id_id unique (company_id, id);

alter table customer_orders
    add column if not exists lead_id uuid;

alter table instagram_comments
    add column if not exists lead_id uuid;

alter table customer_orders
    add constraint fk_customer_orders_crm_lead
    foreign key (company_id, lead_id)
    references crm_leads(company_id, id)
    on delete set null;

alter table instagram_comments
    add constraint fk_instagram_comments_crm_lead
    foreign key (company_id, lead_id)
    references crm_leads(company_id, id)
    on delete set null;

create index if not exists idx_customer_orders_lead_id
    on customer_orders(company_id, lead_id)
    where lead_id is not null;

create index if not exists idx_instagram_comments_lead_id
    on instagram_comments(company_id, lead_id)
    where lead_id is not null;

with ranked as (
    select o.*,
           row_number() over (
               partition by o.company_id, lower(coalesce(o.channel, 'manual')), o.customer_id
               order by o.updated_at desc nulls last, o.created_at desc
           ) as row_rank,
           min(o.created_at) over (
               partition by o.company_id, lower(coalesce(o.channel, 'manual')), o.customer_id
           ) as first_seen,
           max(coalesce(o.updated_at, o.created_at)) over (
               partition by o.company_id, lower(coalesce(o.channel, 'manual')), o.customer_id
           ) as last_seen
    from customer_orders o
    where o.customer_id is not null
), latest as (
    select * from ranked where row_rank = 1
)
insert into crm_leads (
    company_id, platform, external_id, conversation_id,
    first_name, phone, interested_in, status, lead_source,
    first_interaction_at, last_interaction_at, metadata
)
select
    company_id,
    case
        when lower(coalesce(channel, '')) in ('instagram', 'whatsapp') then lower(channel)
        else 'manual'
    end,
    customer_id,
    conversation_id,
    nullif(customer_name, ''),
    nullif(customer_phone, ''),
    nullif(product_title, ''),
    case
        when status in ('paid', 'completed', 'done') then 'enrolled'
        when status = 'accepted' then 'qualified'
        when status = 'cancelled' then 'lost'
        when status = 'sent_to_manager' then 'interested'
        else 'new'
    end,
    case
        when lower(coalesce(channel, '')) = 'instagram' then 'instagram_dm'
        when lower(coalesce(channel, '')) = 'whatsapp' then 'whatsapp_dm'
        else 'course_inquiry'
    end,
    first_seen,
    last_seen,
    jsonb_build_object('backfilled_from', 'customer_orders')
from latest
on conflict (company_id, platform, external_id)
do update set
    first_name = coalesce(excluded.first_name, crm_leads.first_name),
    phone = coalesce(excluded.phone, crm_leads.phone),
    interested_in = coalesce(excluded.interested_in, crm_leads.interested_in),
    status = case
        when crm_leads.status in ('archived', 'not_interested') then crm_leads.status
        else excluded.status
    end,
    first_interaction_at = least(crm_leads.first_interaction_at, excluded.first_interaction_at),
    last_interaction_at = greatest(crm_leads.last_interaction_at, excluded.last_interaction_at),
    updated_at = now();

update customer_orders o
set lead_id = l.id
from crm_leads l
where o.lead_id is null
  and l.company_id = o.company_id
  and l.platform = case
      when lower(coalesce(o.channel, '')) in ('instagram', 'whatsapp') then lower(o.channel)
      else 'manual'
  end
  and l.external_id = o.customer_id;
