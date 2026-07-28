import assert from 'node:assert/strict';
import test from 'node:test';

import { resolveAppView } from '../src/services/routePolicy.ts';

test('anonymous visitors always see the single login view', () => {
  assert.equal(resolveAppView('/', null), 'login');
  assert.equal(resolveAppView('/admin/login', null), 'login');
  assert.equal(resolveAppView('/anything', null), 'login');
});

test('every authenticated role enters the unified workspace', () => {
  assert.equal(resolveAppView('/', 'admin'), 'workspace');
  assert.equal(resolveAppView('/crm', 'company_user'), 'workspace');
});
