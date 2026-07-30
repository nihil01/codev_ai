import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const component = readFileSync(new URL('../src/pages/company/CustomerOrders.tsx', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.tsx', import.meta.url), 'utf8');

test('course inquiry screen shows lead facts instead of commerce controls', () => {
  for (const key of [
    'orders.customer',
    'orders.course',
    'orders.price',
    'orders.channel',
    'orders.date',
    'orders.comment',
  ]) {
    assert.ok(component.includes(`t('${key}')`), `missing ${key}`);
  }

  assert.doesNotMatch(component, /quantity|delivery_required|revenue_amount|cost_amount|markPaid|updateCustomerOrder/);
  assert.match(component, /<table/);
});

test('Azerbaijani navigation names the feature as course inquiries', () => {
  assert.match(i18n, /"tabs\.orders": "Kurs müraciətləri"/);
  assert.match(i18n, /"orders\.course": "Kurs"/);
  assert.doesNotMatch(i18n, /"tabs\.orders": "Sifarişlər"/);
});
