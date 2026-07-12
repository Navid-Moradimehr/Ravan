const { chromium, expect } = require('@playwright/test');
(async () => {
  const launchOptions = { headless: true };
  if (process.env.PLAYWRIGHT_CHROMIUM_PATH) {
    launchOptions.executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH;
  }
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto('http://localhost:3006', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Industrial streaming command center' })).toBeVisible();
  for (const text of ['Kafka control plane', 'Live pipeline summary', 'Current health snapshot', 'Current Stack', 'Operator Links']) {
    await expect(page.getByText(text)).toBeVisible();
  }
  await expect(page.getByRole('link', { name: 'Open pipeline view' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Kafka UI' })).toBeVisible();
  for (const text of ['Pipeline', 'Historian', 'Observability', 'Integrations']) {
    await expect(page.getByRole('link', { name: new RegExp(text) }).first()).toBeVisible();
  }
  await page.getByRole('link', { name: /Pipeline .*Open route/ }).first().click();
  await expect(page.getByRole('heading', { name: 'Extraction, normalization, processing, and DLQ boundaries' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Processing runtime' })).toBeVisible();
  await page.goto('http://localhost:3006/processing', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Extraction, normalization, processing, and DLQ boundaries' })).toBeVisible();
  await page.goto('http://localhost:3006/historian', { waitUntil: 'networkidle' });
  await expect(page.getByText('Custom Dashboard')).toBeVisible();
  await expect(page.getByText('Historian overview')).toBeVisible();
  await page.getByRole('button', { name: 'Add panel' }).click();
  await expect(page.getByRole('button', { name: /Historian trend/ })).toBeVisible();
  await page.getByRole('button', { name: /Historian trend/ }).click();
  await expect(page.getByText('Open Settings and choose an asset tag to configure this trend.')).toBeVisible();
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByRole('button', { name: 'Switch to dark mode' })).toBeVisible();
  await expect(page.getByText('Hardware-free mode')).toBeVisible();
  await page.screenshot({ path: 'docs/dashboard-smoke.png', fullPage: true });
  await browser.close();
})();
