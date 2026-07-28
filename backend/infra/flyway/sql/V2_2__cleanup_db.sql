ALTER TABLE instagram_companies drop column app_scoped_user_id;
ALTER TABLE instagram_companies drop column status;
ALTER TABLE instagram_companies drop column deleted_at;
ALTER TABLE  instagram_system_prompts drop column is_active;

DROP TABLE  instagram_token_refresh_logs;
DROP TABLE instagram_data_deletion_requests;