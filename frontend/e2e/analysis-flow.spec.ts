import { expect, test, type Page } from '@playwright/test';

const BACKEND_BASE_URL = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const ANALYST_TOKEN = process.env.VITE_API_BEARER_TOKEN;

const SAMPLE_JPEG = Buffer.from([
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
  0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xdb, 0x00, 0x43,
  0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
  0x09, 0x08, 0x0a, 0x0c, 0x14, 0x0d, 0x0c, 0x0b, 0x0b, 0x0c, 0x19, 0x12,
  0x13, 0x0f, 0x14, 0x1d, 0x1a, 0x1f, 0x1e, 0x1d, 0x1a, 0x1c, 0x1c, 0x20,
  0x24, 0x2e, 0x27, 0x20, 0x22, 0x2c, 0x23, 0x1c, 0x1c, 0x28, 0x37, 0x29,
  0x2c, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1f, 0x27, 0x39, 0x3d, 0x38, 0x32,
  0x3c, 0x2e, 0x33, 0x34, 0x32, 0xff, 0xc0, 0x00, 0x0b, 0x08, 0x00, 0x01,
  0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xff, 0xc4, 0x00, 0x1f, 0x00, 0x00,
  0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
  0x09, 0x0a, 0x0b, 0xff, 0xc4, 0x00, 0xb5, 0x10, 0x00, 0x02, 0x01, 0x03,
  0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7d,
  0xff, 0xda, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3f, 0x00, 0x7b, 0x94,
  0x11, 0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0xd9,
]);

test.describe.configure({ mode: 'serial' });

async function submitAnalysis(
  page: Page,
  options: {
    noradId: string;
    assetType: string;
    context: string;
  },
) {
  await page.goto('/');
  await page.getByTestId('upload-input').setInputFiles({
    name: `orbital-inspection-${options.noradId}.jpg`,
    mimeType: 'image/jpeg',
    buffer: SAMPLE_JPEG,
  });
  await page.getByTestId('asset-type-select').selectOption(options.assetType);
  await page.getByTestId('norad-input').fill(options.noradId);
  await page.getByTestId('context-input').fill(options.context);
  await page.getByTestId('analyze-button').click();
}

async function useRoleToken(page: Page, role: 'analyst' | 'admin') {
  const token =
    role === 'admin'
      ? process.env.ORBITAL_INSPECT_E2E_ADMIN_TOKEN
      : process.env.VITE_API_BEARER_TOKEN;
  if (!token) {
    throw new Error(`Missing E2E token for role: ${role}`);
  }
  await page.addInitScript(
    ([storageKey, authToken]) => {
      window.localStorage.setItem(storageKey, authToken);
    },
    ['orbitalInspectAuthToken', token],
  );
}

async function fetchJsonWithAuth(page: Page, path: string) {
  if (!ANALYST_TOKEN) {
    throw new Error('Missing analyst E2E token');
  }

  const response = await page.context().request.get(`${BACKEND_BASE_URL}${path}`, {
    headers: {
      Authorization: `Bearer ${ANALYST_TOKEN}`,
    },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test('completed durable analysis persists into portfolio', async ({ page }) => {
  await submitAnalysis(page, {
    noradId: '910001',
    assetType: 'compute_platform',
    context: '[e2e:success] Orbital compute inspection for live Playwright verification.',
  });

  await expect(page.getByTestId('analysis-status')).toHaveText('ASSESSMENT COMPLETE');
  await expect(page.getByTestId('underwriting-badge')).toContainText('INSURABLE');
  await expect(page.getByTestId('risk-tier')).toHaveText('LOW');

  await page.getByTestId('nav-portfolio').click();
  await expect(page.getByTestId('portfolio-view')).toBeVisible();
  await expect(page.getByTestId('portfolio-satellite-card').filter({ hasText: '#910001' })).toContainText('LOW');
});

test('partial durable analysis renders degraded underwriting state', async ({ page }) => {
  await submitAnalysis(page, {
    noradId: '910002',
    assetType: 'solar_array',
    context: '[e2e:partial] Partial evidence path for live Playwright verification.',
  });

  await expect(page.getByTestId('analysis-status')).toHaveText('PARTIAL ASSESSMENT');
  await expect(page.getByTestId('partial-assessment-banner')).toBeVisible();
  await expect(page.getByTestId('underwriting-badge')).toContainText('FURTHER');
});

test('failed terminal state is surfaced clearly', async ({ page }) => {
  await submitAnalysis(page, {
    noradId: '910003',
    assetType: 'servicer',
    context: '[e2e:failed] Failure path for live Playwright verification.',
  });

  await expect(page.getByTestId('analysis-status')).toHaveText('ASSESSMENT FAILED');
  await expect(page.getByTestId('analysis-failed-banner')).toContainText('Underwriting model failed');
});

test('rejected terminal state is surfaced clearly', async ({ page }) => {
  await submitAnalysis(page, {
    noradId: '910004',
    assetType: 'other',
    context: '[e2e:rejected] Rejection path for live Playwright verification.',
  });

  await expect(page.getByTestId('analysis-status')).toHaveText('TARGET REJECTED');
  await expect(page.getByTestId('analysis-rejected-banner')).toBeVisible();
});

test('decision workflow supports approve, block, reimage, and override', async ({ page }) => {
  await useRoleToken(page, 'admin');

  await submitAnalysis(page, {
    noradId: '910005',
    assetType: 'compute_platform',
    context: '[e2e:success] Decision approval workflow verification.',
  });

  await expect(page.getByTestId('decision-summary-panel')).toBeVisible();
  await expect(page.getByTestId('decision-approve-button')).toBeVisible();
  await page.getByTestId('decision-approve-button').click();
  await expect(page.getByText(/Approved for use by/i)).toBeVisible();

  await submitAnalysis(page, {
    noradId: '910006',
    assetType: 'compute_platform',
    context: '[e2e:success] Decision block and reimage workflow verification.',
  });

  await expect(page.getByTestId('decision-block-button')).toBeVisible();
  await page.getByTestId('decision-block-button').click();
  await expect(page.getByTestId('decision-reset-button')).toBeVisible();
  await expect(page.getByText(/Blocked:/i)).toBeVisible();
  await page.getByTestId('decision-reset-button').click();
  await expect(page.getByTestId('decision-reimage-button')).toBeVisible();
  await page.getByTestId('decision-reimage-button').click();
  await expect(page.getByText(/^Blocked: Re-image required before decision use$/)).toBeVisible();
  await expect(page.getByText(/^REIMAGE$/).first()).toBeVisible();

  await submitAnalysis(page, {
    noradId: '910007',
    assetType: 'compute_platform',
    context: '[e2e:success] Decision override workflow verification.',
  });

  await expect(page.getByTestId('decision-override-button')).toBeDisabled();
  await page.getByTestId('decision-override-comments-input').fill(
    'Operational context has changed and the asset should stay under monitored operations.',
  );
  await expect(page.getByTestId('decision-override-button')).toBeEnabled();
  await page.getByTestId('decision-override-action-select').selectOption('monitor');
  await page.getByTestId('decision-override-button').click();
  await expect(page.getByText(/Override active/i)).toBeVisible();
  await expect(page.getByText(/Administrative override to monitor/i)).toBeVisible();
});

test('analyst sees decision review controls without admin override controls', async ({ page }) => {
  await submitAnalysis(page, {
    noradId: '910008',
    assetType: 'compute_platform',
    context: '[e2e:success] Analyst permission workflow verification.',
  });

  await expect(page.getByTestId('analysis-status')).toHaveText('ASSESSMENT COMPLETE');
  await expect(page.getByTestId('decision-summary-panel')).toBeVisible();
  await expect(page.getByTestId('decision-approve-button')).toBeVisible();
  await expect(page.getByTestId('decision-block-button')).toBeVisible();
  await expect(page.getByTestId('decision-reimage-button')).toBeVisible();
  await expect(page.getByTestId('decision-override-button')).toHaveCount(0);
  await expect(page.getByText('ADMIN OVERRIDE')).toHaveCount(0);
});

test('report artifact generation returns stored downloadable pdf metadata', async ({ page }) => {
  await submitAnalysis(page, {
    noradId: '910009',
    assetType: 'compute_platform',
    context: '[e2e:success] Report artifact generation verification.',
  });

  await expect(page.getByTestId('analysis-status')).toHaveText('ASSESSMENT COMPLETE');
  await expect(page.getByTestId('download-report-button')).toBeVisible();

  const generateResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      response.url().includes('/api/reports/') &&
      response.url().includes('/generate-pdf'),
  );

  await page.getByTestId('download-report-button').click();
  const generateResponse = await generateResponsePromise;
  expect(generateResponse.ok()).toBeTruthy();
  const payload = (await generateResponse.json()) as {
    report_id: string;
    artifact_kind: string;
    artifact_download_url: string;
  };

  expect(payload.report_id).toBeTruthy();
  expect(payload.artifact_kind).toBe('pdf');
  expect(payload.artifact_download_url).toContain('/api/reports/artifacts/');

  const artifactResponse = await page.context().request.get(
    `${BACKEND_BASE_URL}${payload.artifact_download_url}`,
  );
  expect(artifactResponse.ok()).toBeTruthy();
  expect(artifactResponse.headers()['content-type']).toContain('application/pdf');
  const artifactBody = await artifactResponse.body();
  expect(artifactBody.subarray(0, 4).toString()).toBe('%PDF');

  const reportDetail = (await fetchJsonWithAuth(page, `/api/reports/${payload.report_id}`)) as {
    artifact_kind: string;
    artifact_path: string | null;
    artifact_size_bytes: number | null;
  };
  expect(reportDetail.artifact_kind).toBe('pdf');
  expect(reportDetail.artifact_path).toBeTruthy();
  expect(reportDetail.artifact_size_bytes ?? 0).toBeGreaterThan(100);
});

test('portfolio refresh reflects approved decision state for the reviewed asset', async ({ page }) => {
  await submitAnalysis(page, {
    noradId: '910010',
    assetType: 'compute_platform',
    context: '[e2e:success] Portfolio sync after decision approval verification.',
  });

  await expect(page.getByTestId('analysis-status')).toHaveText('ASSESSMENT COMPLETE');
  await expect(page.getByTestId('decision-approve-button')).toBeVisible();
  await page.getByTestId('decision-approve-button').click();
  await expect(page.getByText(/Approved for use by/i)).toBeVisible();

  await page.getByTestId('nav-portfolio').click();
  await expect(page.getByTestId('portfolio-view')).toBeVisible();
  await page.getByTestId('portfolio-decision-filter').selectOption('approved_for_use');
  await page.getByTestId('portfolio-refresh-button').click();

  const approvedCard = page
    .getByTestId('portfolio-satellite-card')
    .filter({ hasText: '#910010' });
  await expect(approvedCard).toContainText('approved_for_use');
  await expect(approvedCard).toContainText('Approved by analyst-e2e-user');
  await expect(page.getByText('OPEN ATTENTION')).toBeVisible();
});
