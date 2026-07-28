import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const frontendRoot = path.resolve(import.meta.dirname, '..');
const appSource = fs.readFileSync(path.join(frontendRoot, 'src/App.tsx'), 'utf8');

test('every authenticated session uses the single Codev workspace', () => {
  assert.doesNotMatch(appSource, /AdminPanel/);
  assert.match(appSource, /<CompanyDashboard\s+user=\{user\}/);
  assert.doesNotMatch(appSource, /user\.role\s*===\s*['"]admin['"]/);
});
