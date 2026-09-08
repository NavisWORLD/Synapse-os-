import { test, expect } from '@playwright/test';

async function clockIn(page, name) {
  await page.locator('#brain-name').fill(name);
  await page.locator('#brain-clock').click();
  await expect(page.locator('#active-brain')).toContainText(name);
}

async function sendCloudTurn(page, text) {
  const before = await page.locator('.beast-turn.beast').count();
  await page.locator('#beast-message').fill(text);
  await page.locator('#beast-send').click();
  await expect(page.locator('.beast-turn.beast')).toHaveCount(before + 1, { timeout: 60_000 });
  const turn = page.locator('.beast-turn.beast').last().locator('pre');
  await expect(turn).not.toHaveText('');
  await expect(turn).not.toContainText('Turn rejected');
  return (await turn.textContent())?.trim() || '';
}

test('Azure cloud brain runs through Beast while Synapse revokes authority on swap', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /YOUR AI SYSTEM/i })).toBeVisible();
  await expect(page.locator('#cap-bridge')).toHaveText('AUTHORIZED');
  await expect(page.locator('#brain-location')).toHaveText('CLOUD');
  await expect(page.locator('#beast-runtime-live')).toHaveText('CONNECTED');

  await clockIn(page, 'Azure Brain A');
  const first = await sendCloudTurn(
    page,
    'You are the live Azure-hosted brain in a BeastOS verification demo. Reply briefly and include the token AZURE-BRAIN-ONLINE.'
  );
  expect(first.length).toBeGreaterThan(0);

  await page.locator('#grant-capability').selectOption({ label: 'filesystem.write' });
  await page.locator('#grant').click();
  await expect(page.locator('#active-grants')).toContainText('filesystem.write');

  await clockIn(page, 'Azure Brain B');
  await expect(page.locator('#active-grants')).toHaveText('NONE');
  const second = await sendCloudTurn(
    page,
    'Reply briefly that the cloud brain is still online after the brain swap. Do not claim any local device permission.'
  );
  expect(second.length).toBeGreaterThan(0);

  await page.locator('#trace-refresh').click();
  await expect(page.locator('#trace-output')).toContainText('brain_clock_in');
  await expect(page.locator('#trace-output')).toContainText('beast_chat');
  const trace = await page.locator('#trace-output').textContent();
  expect(trace).not.toContain('AZURE-BRAIN-ONLINE');
  expect(trace).not.toContain('live Azure-hosted brain');

  await page.screenshot({ path: 'test-results/azure-live-final.png', fullPage: true });
});
