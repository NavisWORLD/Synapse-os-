import { test, expect } from '@playwright/test';

async function clockIn(page, name) {
  await page.locator('#brain-name').fill(name);
  await page.locator('#brain-clock').click();
  await expect(page.locator('#active-brain')).toContainText(name);
}

async function sendBeastTurn(page, text) {
  await page.locator('#beast-message').fill(text);
  const before = await page.locator('.beast-turn.beast').count();
  await page.locator('#beast-send').click();
  await expect(page.locator('.beast-turn.beast')).toHaveCount(before + 1);
}

test('real Beast continuity survives brain swap while authority resets', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /YOUR AI SYSTEM/i })).toBeVisible();
  await expect(page.locator('#cap-bridge')).toHaveText('AUTHORIZED');
  await expect(page.locator('#beast-runtime-live')).toHaveText('CONNECTED');

  await clockIn(page, 'Brain A');
  await sendBeastTurn(page, 'BeastOS browser continuity seed alpha.');

  await page.locator('#grant-capability').selectOption({ label: 'filesystem.write' });
  await page.locator('#grant').click();
  await expect(page.locator('#active-grants')).toContainText('filesystem.write');

  await clockIn(page, 'Brain B');
  await expect(page.locator('#active-grants')).toHaveText('NONE');
  await sendBeastTurn(page, 'Continue after the brain swap without inheriting prior keys.');

  await page.locator('#beast-inspect').click();
  await expect(page.locator('#beast-inspect-output')).not.toContainText(/unavailable|error/i);

  await page.locator('#trace-refresh').click();
  await expect(page.locator('#trace-output')).toContainText('brain_clock_in');
  await expect(page.locator('#trace-output')).toContainText('beast_chat');
  const trace = await page.locator('#trace-output').textContent();
  expect(trace).not.toContain('BeastOS browser continuity seed alpha.');
});

test('camera denial is reported and file upload stays temporary', async ({ browser }) => {
  const context = await browser.newContext({ permissions: [] });
  const page = await context.newPage();
  await page.goto('/');
  await clockIn(page, 'Permission Test Brain');

  await page.locator('#camera-start').click();
  await expect(page.locator('#cap-camera')).toHaveText('DENIED');
  await expect(page.locator('#active-grants')).not.toContainText('camera');

  await page.locator('#file-picker').setInputFiles({
    name: 'temporary-note.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('temporary only'),
  });
  await expect(page.locator('#file-list')).toContainText('temporary-note.txt');
  await expect(page.locator('#file-list')).toContainText('TEMPORARY_ATTACHMENT');
  await context.close();
});

test('master privacy revokes active bridge authority', async ({ page }) => {
  await page.goto('/');
  await clockIn(page, 'Privacy Brain');
  await page.locator('#grant-capability').selectOption({ label: 'filesystem.write' });
  await page.locator('#grant').click();
  await expect(page.locator('#active-grants')).toContainText('filesystem.write');
  await page.locator('#privacy-stop').click();
  await expect(page.locator('#active-grants')).toHaveText('NONE');
});

test('installed PWA shell reloads offline without fabricating API responses', async ({ page, context }) => {
  await page.goto('/');
  await page.evaluate(() => navigator.serviceWorker.ready);
  await context.setOffline(true);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await expect(page.getByRole('heading', { name: /YOUR AI SYSTEM/i })).toBeVisible();
  await expect(page.locator('#cap-bridge')).toHaveText('UNAVAILABLE');
  await context.setOffline(false);
});
