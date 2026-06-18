const { chromium, expect } = require('@playwright/test');
(async () => {
  const launchOptions = { headless: true };
  if (process.env.PLAYWRIGHT_CHROMIUM_PATH) {
    launchOptions.executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH;
  }
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Real-time streaming and BI control plane.' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Signal Map' })).toBeVisible();
  for (const text of ['Ingest target', 'Latency budget', 'CDC source', 'Runtime', 'AI Gateway', 'Operator Links']) {
    await expect(page.getByText(text)).toBeVisible();
  }
  for (const text of ['Open Redpanda Console', 'Grafana', 'Prometheus', 'Flink UI', 'AI Health']) {
    await expect(page.getByRole('link', { name: text })).toBeVisible();
  }
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByRole('button', { name: 'Switch to dark mode' })).toBeVisible();
  const content = await page.content();
  if (!content.includes('openai/gpt-oss-20B')) throw new Error('model not rendered');
  await page.screenshot({ path: 'docs/dashboard-smoke.png', fullPage: true });
  await browser.close();
})();
