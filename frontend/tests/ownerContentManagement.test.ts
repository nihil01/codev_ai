import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const root = new URL('../src/', import.meta.url);
const posts = readFileSync(new URL('pages/company/PostsSchedulerPanel.tsx', root), 'utf8');
const api = readFileSync(new URL('api.ts', root), 'utf8');
const dashboard = readFileSync(new URL('pages/company/CompanyDashboard.tsx', root), 'utf8');
const socialConnections = readFileSync(new URL('pages/company/SocialConnectionsPage.tsx', root), 'utf8');
const i18n = readFileSync(new URL('i18n.tsx', root), 'utf8');
const admin = readFileSync(new URL('pages/admin/AdminPanel.tsx', root), 'utf8');

test('manual post calendar exposes LinkedIn without AI generation', () => {
  assert.match(posts, /linkedin/);
  assert.doesNotMatch(posts, /Replicate|Sparkles|generateReplicateVideo|aiPrompt|aiCaption/);
  assert.doesNotMatch(api, /createReplicateProductVideo|replicate-product-video|monthly_ai_videos|ai_videos_used/);
  assert.doesNotMatch(i18n, /Replicate|AI video|AI-видео|monthly_ai_videos|ai_videos_used/);
  assert.doesNotMatch(admin, /Replicate|AI videos|monthly_ai_videos|ai_videos_used/);
});

test('owner workspace exposes prompt and LinkedIn connection contracts', () => {
  assert.match(api, /\/api\/tenants\/\$\{tenantId\}\/bot-prompt/);
  assert.match(api, /\/api\/tenants\/\$\{tenantId\}\/linkedin/);
  assert.match(dashboard, /SocialConnectionsPage/);
  assert.match(socialConnections, /LinkedInSettings/);
  assert.match(dashboard, /BotPromptSettings/);
});
