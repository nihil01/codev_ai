import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const frontendRoot = path.resolve(import.meta.dirname, '..');
const sourceRoot = path.join(frontendRoot, 'src');

function read(relativePath: string) {
  return fs.readFileSync(path.join(sourceRoot, relativePath), 'utf8');
}

const authLayout = read('components/layout/AuthLayout.tsx');
const loginForm = read('pages/auth/LoginForm.tsx');
const dashboardShell = read('components/layout/DashboardShell.tsx');
const companyDashboard = read('pages/company/CompanyDashboard.tsx');
const translations = read('i18n.tsx');
const platformPages = [
  'pages/company/InstagramSettings.tsx',
  'pages/company/WhatsAppSettings.tsx',
  'pages/company/TikTokSettings.tsx',
  'pages/company/LinkedInSettings.tsx',
].map(read);

test('client UI omits redundant workspace copy and provider branding', () => {
  const visibleClientSource = [authLayout, loginForm, dashboardShell, companyDashboard, translations, ...platformPages].join('\n');

  for (const text of ['Vahid iş məkanı', 'Codev iş məkanı', 'Təhlükəsiz giriş', 'Şəxsi iş məkanınız', 'Şəxsi iş məkanı']) {
    assert.doesNotMatch(visibleClientSource, new RegExp(text));
  }
  assert.doesNotMatch(translations, /Zernio/i);
  assert.doesNotMatch(platformPages.join('\n'), />[^<{]*Zernio[^<{]*</i);
});

test('all social connection pages use one shared connection layout', () => {
  for (const page of platformPages) {
    assert.match(page, /import \{ SocialIntegrationLayout \}/);
    assert.match(page, /<SocialIntegrationLayout/);
  }
});
