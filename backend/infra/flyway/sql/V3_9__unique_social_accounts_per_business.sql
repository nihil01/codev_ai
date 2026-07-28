-- One external social account must belong to one local business only.
-- The old per-company constraints allowed the same Zernio account to be inserted for several companies.

create unique index if not exists ux_zernio_instagram_connected_accounts_account
    on zernio_instagram_connected_accounts(zernio_account_id);

create unique index if not exists ux_zernio_instagram_connected_accounts_external_account
    on zernio_instagram_connected_accounts(instagram_account_id)
    where instagram_account_id is not null;

create unique index if not exists ux_zernio_whatsapp_connected_accounts_account
    on zernio_whatsapp_connected_accounts(zernio_account_id);

create unique index if not exists ux_zernio_whatsapp_connected_accounts_external_account
    on zernio_whatsapp_connected_accounts(whatsapp_account_id)
    where whatsapp_account_id is not null;
