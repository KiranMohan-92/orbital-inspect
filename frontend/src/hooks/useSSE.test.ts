import { describe, expect, it, vi } from 'vitest';

import { consumeSSEStream } from './useSSE';

function makeResponse(body: string): Response {
  return new Response(body, {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

describe('consumeSSEStream', () => {
  it('accepts an explicit terminal done event', async () => {
    const onAgentEvent = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    const response = makeResponse(
      'event: done\ndata: {"status":"completed_partial"}\n\n',
    );

    await consumeSSEStream(response, { onAgentEvent, onDone, onError });

    expect(onDone).toHaveBeenCalledWith('completed_partial');
    expect(onError).not.toHaveBeenCalled();
    expect(onAgentEvent).not.toHaveBeenCalled();
  });

  it('fails closed when the stream ends without a terminal event', async () => {
    const onAgentEvent = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    const response = makeResponse(
      [
        'event: agent_event',
        'data: {"agent":"orbital_classification","status":"thinking","payload":{"message":"working"},"timestamp":1,"analysis_id":"analysis-1","event_id":"evt-1","sequence":0,"schema_version":"2.0","degraded":false}',
        '',
      ].join('\n'),
    );

    await expect(
      consumeSSEStream(response, { onAgentEvent, onDone, onError }),
    ).rejects.toThrow('Analysis stream ended unexpectedly before terminal status');

    expect(onAgentEvent).toHaveBeenCalledTimes(1);
    expect(onDone).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });
});
