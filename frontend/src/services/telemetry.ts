/**
 * Frontend error telemetry service.
 * Captures unhandled exceptions, failed API calls, and SSE disconnections.
 * Reports to the backend metrics endpoint for OTel forwarding.
 */

interface TelemetryEvent {
  type: 'error' | 'api_failure' | 'sse_disconnect' | 'performance';
  message: string;
  source?: string;
  stack?: string;
  url?: string;
  status?: number;
  timestamp: number;
  userAgent: string;
  sessionId: string;
}

const SESSION_ID = crypto.randomUUID?.() || Math.random().toString(36).slice(2);
const EVENT_BUFFER: TelemetryEvent[] = [];
const FLUSH_INTERVAL = 30_000; // 30 seconds
const MAX_BUFFER = 50;

function createEvent(partial: Omit<TelemetryEvent, 'timestamp' | 'userAgent' | 'sessionId'>): TelemetryEvent {
  return {
    ...partial,
    timestamp: Date.now(),
    userAgent: navigator.userAgent,
    sessionId: SESSION_ID,
  };
}

export function captureError(error: Error, source?: string): void {
  EVENT_BUFFER.push(createEvent({
    type: 'error',
    message: error.message,
    source: source || 'unknown',
    stack: error.stack?.slice(0, 1000),
  }));
  if (EVENT_BUFFER.length >= MAX_BUFFER) flush();
}

export function captureApiFailure(url: string, status: number, message: string): void {
  EVENT_BUFFER.push(createEvent({
    type: 'api_failure',
    message,
    url,
    status,
  }));
}

export function captureSseDisconnect(url: string, reason: string): void {
  EVENT_BUFFER.push(createEvent({
    type: 'sse_disconnect',
    message: reason,
    url,
  }));
}

async function flush(): Promise<void> {
  if (EVENT_BUFFER.length === 0) return;
  const events = EVENT_BUFFER.splice(0, MAX_BUFFER);
  try {
    // Best-effort — don't block or retry telemetry itself
    await fetch('/api/v1/telemetry/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ events }),
    }).catch(() => {}); // Silent fail for telemetry
  } catch {
    // Telemetry should never crash the app
  }
}

export function initTelemetry(): void {
  // Global error handler
  window.addEventListener('error', (event) => {
    captureError(event.error || new Error(event.message), 'window.onerror');
  });

  // Unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    const error = event.reason instanceof Error ? event.reason : new Error(String(event.reason));
    captureError(error, 'unhandledrejection');
  });

  // Periodic flush
  setInterval(flush, FLUSH_INTERVAL);

  // Flush on page unload
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flush();
  });
}
