import { describe, expect, it } from 'vitest';

import { readApiErrorMessage } from './api';

describe('readApiErrorMessage', () => {
  it('extracts detail from JSON error payloads', async () => {
    const response = new Response(JSON.stringify({ detail: 'Decision review failed hard' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    });

    await expect(readApiErrorMessage(response, 'Fallback')).resolves.toBe(
      'Decision review failed hard',
    );
  });

  it('falls back to status-bearing message when payload is empty', async () => {
    const response = new Response('', {
      status: 403,
      headers: { 'Content-Type': 'text/plain' },
    });

    await expect(readApiErrorMessage(response, 'Decision review failed')).resolves.toBe(
      'Decision review failed (403)',
    );
  });
});
