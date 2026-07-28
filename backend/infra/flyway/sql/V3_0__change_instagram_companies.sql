ALTER TABLE instagram_companies RENAME COLUMN username TO instagram_username;
ALTER TABLE instagram_companies DROP COLUMN ig_activated;
ALTER TABLE instagram_companies DROP COLUMN wp_activated;

ALTER TABLE users ADD COLUMN ig_activated BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN wp_activated BOOLEAN DEFAULT FALSE;
