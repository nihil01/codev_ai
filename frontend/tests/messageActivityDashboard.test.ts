import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

const frontendRoot = path.resolve(import.meta.dirname, '..');
const source = (relativePath: string) => fs.readFileSync(path.join(frontendRoot, relativePath), 'utf8');

test('overview is message activity only and excludes commerce analytics', () => {
  const dashboard = source('src/components/charts/DashboardCharts.tsx');

  assert.match(dashboard, /api\.messageActivity/);
  assert.match(dashboard, /today_customers/);
  assert.match(dashboard, /top_customers/);

  for (const forbidden of [
    'businessAnalytics',
    'customerOrders',
    'gross_revenue',
    'net_profit',
    'top_products',
    'conversion_rate',
    'stale_inventory_items',
  ]) {
    assert.doesNotMatch(dashboard, new RegExp(forbidden));
  }
});

test('company settings omit redundant helper copy', () => {
  const companyInfo = source('src/pages/company/CompanyInfo.tsx');

  assert.doesNotMatch(companyInfo, /Используйте пароль не короче 8 символов/);
  assert.doesNotMatch(companyInfo, /Основные данные подключённой компании/);
});

test('message activity is loading-, tenant-, race-, and Baku-time-safe', () => {
  const dashboard = source('src/components/charts/DashboardCharts.tsx');
  const api = source('src/api.ts');

  assert.match(dashboard, /const BAKU_TIME_ZONE = 'Asia\/Baku'/);
  assert.equal((dashboard.match(/timeZone: BAKU_TIME_ZONE/g) ?? []).length, 2);
  assert.match(dashboard, /function DashboardSkeleton/);
  assert.match(dashboard, /useLayoutEffect\(\(\) => \{/);
  assert.match(dashboard, /requestGeneration = useRef/);
  assert.match(dashboard, /requestController = useRef<AbortController/);
  assert.match(dashboard, /requestController\.current\?\.abort\(\)/);
  assert.match(dashboard, /generation === requestGeneration\.current/);
  assert.match(dashboard, /setActivity\(EMPTY_ACTIVITY\)/);
  assert.match(api, /messageActivity: .*signal\?: AbortSignal/);
  assert.match(api, /\{ signal \}/);
});
