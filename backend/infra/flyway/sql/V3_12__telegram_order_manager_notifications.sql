alter table order_manager_notifications
    add column if not exists telegram_manager_id uuid references telegram_company_managers(id) on delete set null;

alter table order_manager_notifications drop constraint if exists order_manager_notifications_channel_check;

alter table order_manager_notifications
    add constraint order_manager_notifications_channel_check
        check (channel in ('instagram', 'whatsapp', 'telegram'));

create index if not exists ix_order_manager_notifications_telegram_manager
    on order_manager_notifications(telegram_manager_id);
