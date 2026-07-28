alter table customer_orders
    add column if not exists revenue_amount numeric(12,2),
    add column if not exists cost_amount numeric(12,2),
    add column if not exists paid_at timestamptz,
    add column if not exists completed_at timestamptz,
    add column if not exists cancelled_at timestamptz;

alter table customer_orders drop constraint if exists customer_orders_status_check;

alter table customer_orders
    add constraint customer_orders_status_check
        check (status in ('new', 'sent_to_manager', 'accepted', 'paid', 'completed', 'cancelled', 'done'));

create index if not exists ix_customer_orders_company_paid_at
    on customer_orders(company_id, paid_at);

create index if not exists ix_customer_orders_company_cancelled_at
    on customer_orders(company_id, cancelled_at);
