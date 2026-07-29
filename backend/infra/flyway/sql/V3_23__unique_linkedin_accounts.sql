do $$
declare
    conflicting_accounts text;
begin
    select string_agg(
        external_account_id || ' => companies [' || company_ids || ']',
        '; '
    )
    into conflicting_accounts
    from (
        select
            external_account_id,
            string_agg(company_id::text, ', ' order by company_id::text) as company_ids
        from social_posting_connections
        where platform = 'linkedin'
          and status = 'connected'
          and external_account_id is not null
        group by external_account_id
        having count(distinct company_id) > 1
    ) duplicates;

    if conflicting_accounts is not null then
        raise exception 'Cannot enforce LinkedIn account ownership; resolve duplicate connections first: %', conflicting_accounts;
    end if;
end
$$;

create unique index if not exists ux_social_posting_connections_linkedin_account
    on social_posting_connections(external_account_id)
    where platform = 'linkedin'
      and status = 'connected'
      and external_account_id is not null;
