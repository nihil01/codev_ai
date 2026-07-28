alter table company_automation_settings
    add column if not exists instagram_comments_enabled boolean not null default true;
