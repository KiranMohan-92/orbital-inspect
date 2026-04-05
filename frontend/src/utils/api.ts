const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const AUTH_TOKEN_STORAGE_KEY = "orbitalInspectAuthToken";
const API_KEY_STORAGE_KEY = "orbitalInspectApiKey";

function readStoredValue(key: string): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(key) || window.sessionStorage.getItem(key);
}

export function apiUrl(path: string): string {
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

export function buildApiHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const bearerToken = readStoredValue(AUTH_TOKEN_STORAGE_KEY) || import.meta.env.VITE_API_BEARER_TOKEN;
  const apiKey = readStoredValue(API_KEY_STORAGE_KEY) || import.meta.env.VITE_API_KEY;

  if (bearerToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${bearerToken}`);
  }
  if (apiKey && !headers.has("X-API-Key")) {
    headers.set("X-API-Key", apiKey);
  }
  return headers;
}

export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(apiUrl(path), {
    ...init,
    headers: buildApiHeaders(init?.headers),
  });
}

export async function readApiErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
      const payload = (await response.json()) as Record<string, unknown>;
      const message =
        payload.detail ||
        payload.message ||
        payload.error;
      if (typeof message === 'string' && message.trim()) {
        return message.trim();
      }
    } else {
      const text = await response.text();
      if (text.trim()) {
        return text.trim();
      }
    }
  } catch {
    // Fall through to the generic fallback below.
  }

  return `${fallback} (${response.status})`;
}
