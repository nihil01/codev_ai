alter table instagram_companies
    add column if not exists instagram_account_type varchar(64),
    add column if not exists instagram_profile_picture_url text;
