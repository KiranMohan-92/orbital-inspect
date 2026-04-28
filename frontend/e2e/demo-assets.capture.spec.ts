import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../..');
const assetsDir = path.resolve(repoRoot, 'docs/demo/assets');
const backendBaseUrl = process.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const analystToken = process.env.VITE_API_BEARER_TOKEN;
const adminToken = process.env.ORBITAL_INSPECT_E2E_ADMIN_TOKEN;

const UPLOAD_IMAGE = Buffer.from(
  `
<svg width="1600" height="900" viewBox="0 0 1600 900" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="space" x1="200" y1="80" x2="1360" y2="820" gradientUnits="userSpaceOnUse">
      <stop stop-color="#050816"/>
      <stop offset="1" stop-color="#0A244A"/>
    </linearGradient>
    <radialGradient id="earthGlow" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(1240 860) rotate(-116) scale(640 520)">
      <stop stop-color="#4CD7FF" stop-opacity="0.85"/>
      <stop offset="1" stop-color="#4CD7FF" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="panelBlue" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#6BD8FF"/>
      <stop offset="1" stop-color="#245BCE"/>
    </linearGradient>
  </defs>
  <rect width="1600" height="900" fill="url(#space)"/>
  <circle cx="240" cy="140" r="2.2" fill="#EAF2FF"/>
  <circle cx="420" cy="210" r="1.7" fill="#EAF2FF"/>
  <circle cx="520" cy="120" r="1.4" fill="#EAF2FF"/>
  <circle cx="790" cy="160" r="1.8" fill="#EAF2FF"/>
  <circle cx="980" cy="90" r="2.0" fill="#EAF2FF"/>
  <circle cx="1170" cy="210" r="1.5" fill="#EAF2FF"/>
  <circle cx="1380" cy="150" r="2.1" fill="#EAF2FF"/>
  <circle cx="1450" cy="320" r="1.4" fill="#EAF2FF"/>
  <path d="M816 772C1015 750 1263 773 1506 900H966C883 900 779 888 662 852C558 820 456 770 346 694C454 746 617 786 816 772Z" fill="url(#earthGlow)"/>
  <ellipse cx="1160" cy="864" rx="520" ry="156" fill="#103A75"/>
  <ellipse cx="1160" cy="864" rx="520" ry="156" fill="url(#earthGlow)"/>
  <path d="M664 505C664 482 682 464 705 464H896C919 464 937 482 937 505V565C937 588 919 606 896 606H705C682 606 664 588 664 565V505Z" fill="#D6DEE9"/>
  <path d="M704 480H897C911 480 922 491 922 505V564C922 578 911 590 897 590H704C690 590 678 578 678 564V505C678 491 690 480 704 480Z" fill="#6C7787"/>
  <rect x="478" y="470" width="166" height="136" rx="10" fill="url(#panelBlue)" stroke="#9EEAFF" stroke-width="4"/>
  <rect x="955" y="470" width="166" height="136" rx="10" fill="url(#panelBlue)" stroke="#9EEAFF" stroke-width="4"/>
  <line x1="644" y1="538" x2="678" y2="538" stroke="#D6DEE9" stroke-width="10"/>
  <line x1="922" y1="538" x2="955" y2="538" stroke="#D6DEE9" stroke-width="10"/>
  <rect x="764" y="412" width="72" height="68" rx="10" fill="#C6CEDA"/>
  <rect x="785" y="350" width="30" height="66" rx="8" fill="#CFD8E4"/>
  <path d="M800 349V305" stroke="#CFD8E4" stroke-width="8" stroke-linecap="round"/>
  <circle cx="800" cy="300" r="12" fill="#9EEAFF"/>
  <circle cx="1002" cy="532" r="86" stroke="#FF7A7A" stroke-width="6" stroke-dasharray="16 16"/>
  <rect x="958" y="486" width="88" height="92" rx="8" fill="#3F6FDE" fill-opacity="0.25" stroke="#FF7A7A" stroke-width="5"/>
</svg>
`.trim(),
  'utf-8',
);

test.describe.configure({ mode: 'serial' });

test('capture demo media assets', async ({ page }) => {
  await fs.mkdir(assetsDir, { recursive: true });

  await useRoleToken(page, 'admin');
  await seedPortfolio(page.context().request);

  await submitAnalysis(page, {
    noradId: '25544',
    assetType: 'solar_array',
    assetName: 'ISS Solar Array Wing 2B',
    externalAssetId: 'iss-saw-2b',
    context:
      '[e2e:success] README demo capture for debris strike assessment with persisted decision workflow.',
  });

  await expect(page.getByTestId('analysis-status')).toHaveText('ASSESSMENT COMPLETE');
  await expect(page.getByTestId('decision-summary-panel')).toBeVisible();
  await expect(page.getByTestId('download-report-button')).toBeVisible();
  await page.waitForTimeout(1200);

  await page.screenshot({
    path: path.join(assetsDir, 'orbital-inspect-demo-hero.png'),
  });

  await page.getByTestId('analysis-visual-panel').screenshot({
    path: path.join(assetsDir, 'orbital-inspect-demo-analyze.png'),
  });

  await page.getByTestId('analysis-report-panel').evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  await page.waitForTimeout(250);
  await page.getByTestId('analysis-report-panel').screenshot({
    path: path.join(assetsDir, 'orbital-inspect-demo-decision.png'),
  });

  await page.getByTestId('decision-approve-button').click();
  await expect(page.getByText(/Approved for use by/i)).toBeVisible();

  await page.getByTestId('nav-portfolio').click();
  await expect(page.getByTestId('portfolio-view')).toBeVisible();
  await page.getByTestId('portfolio-refresh-button').click();
  await expect(page.getByTestId('portfolio-satellite-card').first()).toBeVisible();
  await expect(page.getByTestId('portfolio-asset-detail-panel')).toBeVisible();
  await page.waitForTimeout(1200);
  await page.screenshot({
    path: path.join(assetsDir, 'orbital-inspect-demo-portfolio.png'),
  });
});

async function useRoleToken(page: Page, role: 'analyst' | 'admin') {
  const token = role === 'admin' ? adminToken : analystToken;
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

async function submitAnalysis(
  page: Page,
  options: {
    noradId: string;
    assetType: string;
    assetName: string;
    externalAssetId: string;
    context: string;
  },
) {
  await page.goto('/');
  await page.getByTestId('upload-input').setInputFiles({
    name: `orbital-demo-${options.noradId}.svg`,
    mimeType: 'image/svg+xml',
    buffer: UPLOAD_IMAGE,
  });
  await page.getByTestId('asset-type-select').selectOption(options.assetType);
  await page.getByTestId('asset-name-input').fill(options.assetName);
  await page.getByTestId('external-asset-id-input').fill(options.externalAssetId);
  await page.getByTestId('norad-input').fill(options.noradId);
  await page.getByTestId('context-input').fill(options.context);
  await page.getByTestId('analyze-button').click();
}

async function seedPortfolio(request: APIRequestContext) {
  if (!adminToken) {
    throw new Error('Missing admin E2E token');
  }

  const seeded = [
    {
      noradId: '39634',
      assetType: 'solar_array',
      assetName: 'Sentinel-1A Array Segment',
      externalAssetId: 'sentinel-1a-array-segment',
      context: '[e2e:partial] README capture seed for partial evidence scenario.',
      decision: null,
    },
    {
      noradId: '20580',
      assetType: 'solar_array',
      assetName: 'Hubble Solar Array Segment',
      externalAssetId: 'hst-array-segment',
      context: '[e2e:success] README capture seed for healthy comparison asset.',
      decision: 'request_reimage',
    },
  ] as const;

  for (const item of seeded) {
    const analysisId = await createPersistedAnalysis(request, item);
    if (item.decision) {
      await reviewDecision(request, analysisId, item.decision);
    }
  }
}

async function createPersistedAnalysis(
  request: APIRequestContext,
  options: {
    noradId: string;
    assetType: string;
    assetName: string;
    externalAssetId: string;
    context: string;
  },
) {
  const response = await request.post(`${backendBaseUrl}/api/analyses`, {
    headers: {
      Authorization: `Bearer ${adminToken}`,
    },
    multipart: {
      image: {
        name: `orbital-demo-${options.noradId}.svg`,
        mimeType: 'image/svg+xml',
        buffer: UPLOAD_IMAGE,
      },
      norad_id: options.noradId,
      asset_type: options.assetType,
      asset_name: options.assetName,
      external_asset_id: options.externalAssetId,
      context: options.context,
    },
  });
  expect(response.ok()).toBeTruthy();
  const payload = (await response.json()) as { analysis_id: string };
  expect(payload.analysis_id).toBeTruthy();
  await waitForTerminalAnalysis(request, payload.analysis_id);
  return payload.analysis_id;
}

async function waitForTerminalAnalysis(request: APIRequestContext, analysisId: string) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    const response = await request.get(`${backendBaseUrl}/api/analyses/${analysisId}`, {
      headers: {
        Authorization: `Bearer ${adminToken}`,
      },
    });
    expect(response.ok()).toBeTruthy();
    const payload = (await response.json()) as { status?: string };
    if (payload.status && ['completed', 'completed_partial', 'failed', 'rejected'].includes(payload.status)) {
      return payload.status;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  throw new Error(`Timed out waiting for analysis ${analysisId}`);
}

async function reviewDecision(
  request: APIRequestContext,
  analysisId: string,
  action: 'approve' | 'block' | 'request_reimage',
) {
  const response = await request.post(`${backendBaseUrl}/api/analyses/${analysisId}/decision/review`, {
    headers: {
      Authorization: `Bearer ${adminToken}`,
      'Content-Type': 'application/json',
    },
    data: {
      action,
      comments:
        action === 'approve'
          ? 'Approved for README capture'
          : action === 'block'
            ? 'Blocked for README capture'
            : 'Re-image required before decision use',
    },
  });
  expect(response.ok()).toBeTruthy();
}
