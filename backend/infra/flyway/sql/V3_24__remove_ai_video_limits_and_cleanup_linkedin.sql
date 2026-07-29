update social_posting_connections
set status = 'disabled',
    external_account_id = null,
    display_name = null,
    metadata = '{}'::jsonb,
    connected_at = null,
    updated_at = now()
where platform = 'linkedin'
  and status = 'connected'
  and (
      coalesce(external_account_id, '') = ''
      or coalesce(metadata->>'zernio_account_id', '') = ''
  );

alter table company_subscriptions
    drop column if exists monthly_ai_videos_limit;

alter table company_usage_counters
    drop column if exists ai_videos_used;
