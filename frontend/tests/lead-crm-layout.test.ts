import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const root = new URL('../src/', import.meta.url);
const dashboard = readFileSync(new URL('pages/company/CompanyDashboard.tsx', root), 'utf8');
const contacts = readFileSync(new URL('pages/company/ContactsPanel.tsx', root), 'utf8');
const api = readFileSync(new URL('api.ts', root), 'utf8');
const posts = readFileSync(new URL('pages/company/PostsSchedulerPanel.tsx', root), 'utf8');
const shell = readFileSync(new URL('components/layout/DashboardShell.tsx', root), 'utf8');
const prompts = readFileSync(new URL('pages/company/BotPromptSettings.tsx', root), 'utf8');
const contactsWorkspace = readFileSync(new URL('pages/company/ContactsWorkspace.tsx', root), 'utf8');

test('all social networks are composed into one connections page', () => {
  assert.match(dashboard, /integrations/);
  assert.doesNotMatch(dashboard, /case 'instagram'|case 'whatsapp'|case 'linkedin'|case 'tiktok'/);
  const page = readFileSync(new URL('pages/company/SocialConnectionsPage.tsx', root), 'utf8');
  for (const component of ['InstagramSettings', 'WhatsAppSettings', 'LinkedInSettings', 'TikTokSettings']) {
    assert.match(page, new RegExp(component));
  }
});

test('lead workspace exposes profile, filters, follow-up, summary, delete and xlsx export', () => {
  for (const contract of ['leads:', 'leadProfile:', 'updateLead:', 'deleteLead:', 'exportLeads:', 'summarizeLead:']) {
    assert.match(api, new RegExp(contract));
  }
  for (const behavior of ['Maraqlandığı kurs', 'Növbəti əlaqə', 'AI xülasəsi', 'XLSX', 'Lead-i sil']) {
    assert.match(contacts, new RegExp(behavior));
  }
});

test('post composer supports multiple media and Instagram stories without native stickers', () => {
  assert.match(posts, /multiple/);
  assert.match(posts, /story/);
  assert.match(posts, /reel/);
  assert.match(posts, /mediaFiles\.length !== 1/);
  assert.match(posts, /selectedPlatforms\.includes\('instagram'\).*mediaFiles\.length > 10/);
  assert.match(posts, /Promise\.allSettled\(created\.map/);
  assert.doesNotMatch(posts, /native.*(?:poll|gift|sticker)/i);
});

test('contacts and course inquiries share one navigation section', () => {
  assert.match(dashboard, /ContactsWorkspace/);
  assert.doesNotMatch(dashboard, /case 'orders'|id: 'orders'/);
  assert.match(contactsWorkspace, /ContactsPanel/);
  assert.match(contactsWorkspace, /CustomerOrders/);
  assert.match(contactsWorkspace, /Kontaktlar/);
  assert.match(contactsWorkspace, /Kurs müraciətləri/);
});

test('lead rows show a manual-change marker before opening the profile', () => {
  assert.match(contacts, /manually_updated_at/);
  assert.match(contacts, /Əl ilə yenilənib/);
  assert.match(api, /manually_updated_by/);
});

test('lead and navigation drawers are accessible and filtered export matches the applied list', () => {
  for (const contract of ['role="dialog"', 'aria-modal="true"', "event.key === 'Escape'", 'data-autofocus']) {
    assert.match(shell, new RegExp(contract));
    assert.match(contacts, new RegExp(contract));
  }
  assert.match(contacts, /appliedFilters/);
  assert.match(contacts, /Daha çox göstər/);
  assert.match(api, /pagination\?\.offset/);
});

test('runtime prompt editors load independently and expose persistent labels', () => {
  assert.match(prompts, /Promise\.allSettled/);
  assert.match(prompts, /intentPrompt/);
  assert.match(prompts, /Söhbət intenti promptu/);
  assert.match(prompts, /htmlFor=\{`\$\{kind\}-prompt-title`\}/);
  assert.match(prompts, /onNotice\(''\)/);
});
