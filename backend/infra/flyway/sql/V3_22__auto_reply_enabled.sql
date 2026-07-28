-- Add auto_reply_enabled column to company_automation_settings
-- This controls whether the bot automatically sends AI-generated replies to Instagram comments

ALTER TABLE company_automation_settings
ADD COLUMN IF NOT EXISTS auto_reply_enabled boolean DEFAULT false;

COMMENT ON COLUMN company_automation_settings.auto_reply_enabled IS 'When true, bot auto-sends AI reply as DM to new Instagram comments';
