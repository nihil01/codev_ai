alter table crm_leads
    drop constraint if exists crm_leads_platform_check;

alter table crm_leads
    add constraint crm_leads_platform_check
    check (platform in ('instagram', 'facebook', 'tiktok', 'whatsapp', 'manual'));
