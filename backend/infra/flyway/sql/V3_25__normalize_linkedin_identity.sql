drop index if exists ux_social_posting_connections_linkedin_account;

update social_posting_connections
set external_account_id = nullif(btrim(external_account_id), ''),
    metadata = case
        when nullif(btrim(coalesce(metadata->>'zernio_account_id', '')), '') is null
            then coalesce(metadata, '{}'::jsonb) - 'zernio_account_id'
        else jsonb_set(
            coalesce(metadata, '{}'::jsonb),
            '{zernio_account_id}',
            to_jsonb(btrim(metadata->>'zernio_account_id')),
            true
        )
    end,
    updated_at = now()
where platform = 'linkedin';

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
      external_account_id is null
      or nullif(btrim(coalesce(metadata->>'zernio_account_id', '')), '') is null
  );

do $$
declare
    conflicting_accounts text;
begin
    select string_agg(
        normalized_account_id || ' => companies [' || company_ids || ']',
        '; '
    )
    into conflicting_accounts
    from (
        select
            btrim(external_account_id) as normalized_account_id,
            string_agg(company_id::text, ', ' order by company_id::text) as company_ids
        from social_posting_connections
        where platform = 'linkedin'
          and status = 'connected'
          and nullif(btrim(external_account_id), '') is not null
        group by btrim(external_account_id)
        having count(distinct company_id) > 1
    ) duplicates;

    if conflicting_accounts is not null then
        raise exception 'Cannot enforce normalized LinkedIn account ownership; resolve duplicate connections first: %', conflicting_accounts;
    end if;
end
$$;

create unique index ux_social_posting_connections_linkedin_account
    on social_posting_connections((btrim(external_account_id)))
    where platform = 'linkedin'
      and status = 'connected'
      and nullif(btrim(external_account_id), '') is not null;

alter table social_posting_connections
    add constraint ck_linkedin_connected_identity_normalized
    check (
        platform <> 'linkedin'
        or status <> 'connected'
        or (
            external_account_id is not null
            and external_account_id = btrim(external_account_id)
            and external_account_id <> ''
            and nullif(btrim(coalesce(metadata->>'zernio_account_id', '')), '') is not null
            and metadata->>'zernio_account_id' = btrim(metadata->>'zernio_account_id')
        )
    ) not valid;

alter table social_posting_connections
    validate constraint ck_linkedin_connected_identity_normalized;
