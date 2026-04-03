import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendPort = 4173;
const backendPort = 8000;
const frontendUrl = `http://127.0.0.1:${frontendPort}`;
const backendUrl = `http://127.0.0.1:${backendPort}`;
const backendDir = path.resolve(__dirname, '../backend');
const e2eRoot = process.env.ORBITAL_INSPECT_E2E_ROOT || `/tmp/orbital_inspect_e2e_${Date.now()}`;
const e2eDbPath = path.join(e2eRoot, 'orbital_inspect.db');
const e2eStorageRoot = path.join(e2eRoot, 'storage');
const useServiceBackedDb =
  process.env.ORBITAL_INSPECT_E2E_USE_POSTGRES === '1' || process.env.CI === 'true';
const e2eDbUrl =
  process.env.ORBITAL_INSPECT_E2E_DATABASE_URL ||
  (useServiceBackedDb
    ? 'postgresql+asyncpg://orbital:orbital_dev_password@127.0.0.1:5432/orbital_inspect_e2e'
    : 'sqlite+aiosqlite:///file:orbital_inspect_e2e?mode=memory&cache=shared&uri=true');
const useMockBackend = process.env.ORBITAL_MOCK_E2E === '1';

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
  webServer: webServers,
});
