alter table social_post_drafts
    drop constraint if exists chk_social_post_drafts_status;

alter table social_post_drafts
    add constraint chk_social_post_drafts_status
    check (status in ('draft', 'pending_review', 'scheduled', 'publishing', 'published', 'failed', 'cancelled', 'rejected'));
