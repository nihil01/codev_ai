import assert from 'node:assert/strict';
import test from 'node:test';

import { readErrorResponse } from '../src/services/httpResponse.ts';

test('error response body is consumed exactly once for JSON errors', async () => {
  const response = new Response(JSON.stringify({ detail: 'Media yüklənmədi' }), {
    status: 503,
    headers: { 'content-type': 'application/json' },
  });

  assert.equal(await readErrorResponse(response), '503 Media yüklənmədi');
  assert.equal(response.bodyUsed, true);
});

test('error response falls back to plain text without reading the body twice', async () => {
  const response = new Response('Storage unavailable', { status: 503 });

  assert.equal(await readErrorResponse(response), '503 Storage unavailable');
  assert.equal(response.bodyUsed, true);
});
