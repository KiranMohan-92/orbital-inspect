import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendPort = 4173;
const backendPort = Number(process.env.ORBITAL_INSPECT_E2E_BACKEND_PORT || '8000');
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const backendUrl = `http://127.0.0.1:${backendPort}`;
const backendDir = path.resolve(__dirname, '../backend');
const e2eRoot = process.env.ORBITAL_INSPECT_E2E_ROOT || `/tmp/orbital_inspect_e2e_${Date.now()}`;
const e2eDbPath = path.join(e2eRoot, 'orbital_inspect.db');
const e2eStorageRoot = path.join(e2eRoot, 'storage');
const useServiceBackedDb =
  process.env.ORBITAL_INSPECT_E2E_USE_POSTGRES === '1' || process.env.CI === 'true';
const useExistingServers = process.env.ORBITAL_CAPTURE_EXISTING_SERVERS === '1';
const includeCaptureTests = process.env.ORBITAL_INCLUDE_CAPTURE_TESTS === '1';
const e2eDbUrl =
  process.env.ORBITAL_INSPECT_E2E_DATABASE_URL ||
  (useServiceBackedDb
    ? 'postgresql+asyncpg://orbital:orbital_dev_password@127.0.0.1:5432/orbital_inspect_e2e'
    : 'sqlite+aiosqlite:///file:orbital_inspect_e2e?mode=memory&cache=shared&uri=true');
const useMockBackend = process.env.ORBITAL_MOCK_E2E === '1';
const e2eJwtSecret =
  process.env.ORBITAL_INSPECT_E2E_JWT_SECRET || 'orbital-inspect-e2e-jwt-secret-2026';

function createHs256Jwt(secret: string, payload: Record<string, unknown>): string {
  const header = { alg: 'HS256', typ: 'JWT' };
  const encode = (value: Record<string, unknown>) =>
    Buffer.from(JSON.stringify(value)).toString('base64url');
  const unsigned = `${encode(header)}.${encode(payload)}`;
  const signature = crypto.createHmac('sha256', secret).update(unsigned).digest('base64url');
  return `${unsigned}.${signature}`;
}

function buildE2eToken(role: 'analyst' | 'admin'): string {
  const now = Math.floor(Date.now() / 1000);
  return createHs256Jwt(e2eJwtSecret, {
    sub: `${role}-e2e-user`,
    org_id: 'org-e2e',
    role,
    iat: now,
    exp: now + 3600,
    type: 'access',
    iss: 'orbital-inspect',
    aud: 'orbital-inspect-api',
  });
}

process.env.ORBITAL_INSPECT_E2E_ROOT = e2eRoot;
process.env.ORBITAL_INSPECT_E2E_DB_PATH = e2eDbPath;
process.env.ORBITAL_INSPECT_E2E_DEMO_CACHE_DIR = path.join(e2eRoot, 'demo_cache');
process.env.ORBITAL_INSPECT_E2E_DEMO_IMAGES_DIR = path.join(backendDir, 'data/demo_images');
process.env.ORBITAL_INSPECT_E2E_DATABASE_URL = e2eDbUrl;
process.env.ORBITAL_INSPECT_E2E_BACKEND_PORT = String(backendPort);
process.env.ORBITAL_INSPECT_E2E_USE_POSTGRES = useServiceBackedDb ? '1' : '0';
process.env.ORBITAL_INSPECT_E2E_STORAGE_ROOT = e2eStorageRoot;
process.env.ORBITAL_INSPECT_E2E_STORAGE_BACKEND =
  process.env.ORBITAL_INSPECT_E2E_STORAGE_BACKEND ||
  process.env.STORAGE_BACKEND ||
  'local';
process.env.ORBITAL_INSPECT_E2E_DATABASE_AUTO_INIT = 'true';
process.env.ORBITAL_INSPECT_E2E_AUTH_ENABLED = 'true';
process.env.ORBITAL_INSPECT_E2E_JWT_SECRET = e2eJwtSecret;
process.env.VITE_API_BASE_URL = process.env.VITE_API_BASE_URL || backendUrl;
process.env.VITE_API_BEARER_TOKEN = process.env.VITE_API_BEARER_TOKEN || buildE2eToken('analyst');
process.env.ORBITAL_INSPECT_E2E_ADMIN_TOKEN =
  process.env.ORBITAL_INSPECT_E2E_ADMIN_TOKEN || buildE2eToken('admin');

const webServers = [
  {
    command: `npm run dev -- --host 127.0.0.1 --port ${frontendPort}`,
    cwd: __dirname,
    url: frontendUrl,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: 'pipe' as const,
    stderr: 'pipe' as const,
  },
];

if (!useMockBackend) {
  webServers.unshift({
    command: 'bash ./e2e/run-backend-e2e.sh',
    cwd: __dirname,
    url: `${backendUrl}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: 'pipe' as const,
    stderr: 'pipe' as const,
  });
}

export default defineConfig({
  testDir: './e2e',
  testIgnore: includeCaptureTests ? [] : ['**/*.capture.spec.ts'],
  fullyParallel: false,
  workers: process.env.CI ? 1 : undefined,
  retries: process.env.CI ? 2 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  globalSetup: './e2e/global-setup.ts',
  use: {
    baseURL: frontendUrl,
    headless: true,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    launchOptions: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : undefined,
  },
  webServer: useExistingServers ? undefined : webServers,
});
