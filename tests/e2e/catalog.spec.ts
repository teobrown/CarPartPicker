import { test, expect } from '@playwright/test';
import { ensureSamplePart } from './setup-data';

test.beforeAll(async () => {
  await ensureSamplePart();
});

test('catalog index lists at least one seeded part', async ({ page }) => {
  await page.goto('/parts');
  await expect(page.locator('h1')).toHaveText('Parts Catalog');
  const items = page.locator('main ul li');
  await expect(items.first()).toBeVisible();
});

test('part detail page shows the vendor block', async ({ page }) => {
  await page.goto('/parts');
  await page.locator('main ul li a').first().click();
  await expect(page.locator('h2')).toHaveText('Vendors');
});
