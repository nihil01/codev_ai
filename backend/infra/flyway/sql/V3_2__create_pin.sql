alter table whatsapp_cloud_integrations
add column if not exists registration_pin text;

alter table whatsapp_cloud_integrations
add column if not exists registered_at timestamptz;