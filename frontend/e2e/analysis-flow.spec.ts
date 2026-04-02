import { expect, test, type Page } from '@playwright/test';

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
