import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const frontendRoot = path.resolve(import.meta.dirname, '..');
const appSource = fs.readFileSync(path.join(frontendRoot, 'src/App.tsx'), 'utf8');
const companySettingsSource = fs.readFileSync(path.join(frontendRoot, 'src/pages/company/CompanyInfo.tsx'), 'utf8');
const i18nSource = fs.readFileSync(path.join(frontendRoot, 'src/i18n.tsx'), 'utf8');

test('every authenticated session uses the single Codev workspace', () => {
  assert.doesNotMatch(appSource, /AdminPanel/);
  assert.match(appSource, /<CompanyDashboard\s+user=\{user\}/);
  assert.doesNotMatch(appSource, /user\.role\s*===\s*['"]admin['"]/);
});

test('company settings exclude business preferences and customer reminders', () => {
  assert.doesNotMatch(companySettingsSource, /companyInfo\.preferencesTitle/);
  assert.doesNotMatch(companySettingsSource, /updateAutomationSettings/);
  assert.doesNotMatch(companySettingsSource, /updateBusinessSettings/);
  assert.doesNotMatch(i18nSource, /Müştəri xatırlatması/);
  assert.doesNotMatch(i18nSource, /Biznes ayarları/);
});
