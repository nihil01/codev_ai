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
      nullif(btrim(coalesce(external_account_id, '')), '') is null
      or nullif(btrim(coalesce(metadata->>'zernio_account_id', '')), '') is null
  );
