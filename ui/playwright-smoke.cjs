const { chromium, expect } = require('@playwright/test');
(async () => {
  const launchOptions = { headless: true };
  if (process.env.PLAYWRIGHT_CHROMIUM_PATH) {
    launchOptions.executablePath = process.env.PLAYWRIGHT_CHROMIUM_PATH;
  }
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.goto('http://localhost:3006', { waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: 'Validate plant data before it reaches the plant.' })).toBeVisible();
  for (const text of ['Normalized stream', 'Burst target', 'Latency budget', 'Exception lane', 'AI Gateway', 'Operator Links']) {
    await expect(page.getByText(text)).toBeVisible();
  }
  for (const text of ['Live throughput', 'LLM p95 latency', 'DLQ total', 'Ingest throughput', 'AI latency', 'Protocol mix', 'Severity mix']) {
    await expect(page.getByText(text)).toBeVisible();
  }
  await expect(page.getByText(/Grafana (online|offline)/).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open Redpanda Console' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Grafana', exact: true })).toBeVisible();
  for (const text of ['Prometheus', 'Edge Metrics', 'AI Health']) {
    await expect(page.getByRole('link', { name: text })).toBeVisible();
  }
  await expect(page.getByRole('link', { name: 'Open local Grafana' })).toHaveAttribute('href', /\/login$/);
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
