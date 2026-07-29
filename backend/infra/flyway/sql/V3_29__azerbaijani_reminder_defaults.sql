-- Keep reminder behavior Azerbaijani-only for both new and already migrated tenants.
ALTER TABLE company_automation_settings
    ALTER COLUMN client_reminder_message
    SET DEFAULT 'Salam! Söhbətimizi nəzakətlə xatırlatmaq istədik. Mövzu hələ aktualdırsa, bizə yazın — kömək etməyə hazırıq.';

UPDATE company_automation_settings
SET client_reminder_message = 'Salam! Söhbətimizi nəzakətlə xatırlatmaq istədik. Mövzu hələ aktualdırsa, bizə yazın — kömək etməyə hazırıq.',
    updated_at = now()
WHERE client_reminder_message = 'Здравствуйте! Хотели мягко напомнить о нашем диалоге. Если вопрос ещё актуален — напишите, мы рядом и поможем.';
