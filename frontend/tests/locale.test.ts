import assert from 'node:assert/strict';
import test from 'node:test';

import { DEFAULT_LOCALE, SUPPORTED_LOCALES } from '../src/services/locale.ts';

test('Codev exposes Azerbaijani as the only interface language', () => {
  assert.equal(DEFAULT_LOCALE, 'az');
  assert.deepEqual(SUPPORTED_LOCALES, ['az']);
});
