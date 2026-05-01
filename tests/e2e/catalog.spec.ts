import { test, expect } from '@playwright/test';
import { ensureSamplePart } from './setup-data';

test.beforeAll(async () => {
  await ensureSamplePart();
});

test('catalog index lists at least one seeded part', async ({ page }) => {
  await page.goto('/parts');
  // page header reads "Catalog" (with a signal-color period appended)
  await expect(page.locator('main h1')).toContainText('Catalog');
  // each part is rendered as a row link to /part/<brand>/<model>
  const partLinks = page.locator('main a[href^="/part/"]');
  await expect(partLinks.first()).toBeVisible();
});

test('part detail page shows the vendor matrix', async ({ page }) => {
  await page.goto('/parts');
  // click the first row link in the catalog
  await page.locator('main a[href^="/part/"]').first().click();
  // the part detail page has a "[VEN] · Vendor matrix" eyebrow + heading
  await expect(page.locator('main')).toContainText('Vendor matrix');
});
