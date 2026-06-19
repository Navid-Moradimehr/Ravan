const { chromium, expect } = require('@playwright/test');
(async () => {
  const launchOptions = { headless: true };
  if (process.env.PLAYWRIGHT_CHROMIUM_PATH) {
    launchOptions.executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH;
  }
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto('http://localhost:3000', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Industrial data command center.' })).toBeVisible();
  for (const text of ['Normalized topic', 'Burst target', 'Latency budget', 'DLQ capture', 'AI Gateway', 'Operator Links']) {
    await expect(page.getByText(text)).toBeVisible();
  }
  for (const text of ['Open Redpanda Console', 'Grafana', 'Prometheus', 'Edge Metrics', 'AI Health']) {
    await expect(page.getByRole('link', { name: text })).toBeVisible();
  }
  for (const text of ['OPC UA', 'MQTT', 'Modbus TCP']) {
    await expect(page.getByText(text).first()).toBeVisible();
  }
  await page.getByRole('tab', { name: 'Test workflow' }).click();
  await expect(page.getByText('scripts/start-industrial-sim.ps1').first()).toBeVisible();
  await page.getByRole('button', { name: 'Switch to light mode' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await expect(page.getByRole('button', { name: 'Switch to dark mode' })).toBeVisible();
  await expect(page.getByText('LM Studio compatible enrichment path')).toBeVisible();
  await page.screenshot({ path: 'docs/dashboard-smoke.png', fullPage: true });
  await browser.close();
})();
