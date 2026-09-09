import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const evidenceDir = path.resolve('test-results/live-demo');

async function clockIn(page, name) {
  await page.locator('#brain-name').fill(name);
  await page.locator('#brain-clock').click();
  await expect(page.locator('#active-brain')).toContainText(name);
}

async function sendTurn(page, text) {
  const before = await page.locator('.beast-turn.beast').count();
  await page.locator('#beast-message').fill(text);
  await page.locator('#beast-send').click();
  await expect(page.locator('.beast-turn.beast')).toHaveCount(before + 1, { timeout: 90_000 });
  const body = page.locator('.beast-turn.beast').last().locator('pre');
  await expect(body).not.toHaveText('');
  const response = ((await body.textContent()) || '').trim();
  expect(response).not.toContain('Turn rejected');
  return response;
}

async function collectCapabilityMatrix(page) {
  const ids = [
    'cap-bridge', 'cap-beast', 'cap-ollama', 'cap-vm', 'cap-camera', 'cap-mic',
    'cap-files', 'cap-opfs', 'cap-webgpu', 'cap-usb', 'cap-serial', 'cap-bluetooth',
    'cap-network', 'cap-wasm', 'cap-wasm-threads', 'cap-wasm-simd', 'browser-network',
  ];
  const out = {};
  for (const id of ids) {
    const node = page.locator(`#${id}`);
    out[id] = await node.count() ? ((await node.textContent()) || '').trim() : 'NOT_ESTABLISHED';
  }
  return out;
}

test('real local Ollama brain talks through Beast and loses authority on brain swap', async ({ page }) => {
  fs.mkdirSync(evidenceDir, { recursive: true });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /YOUR AI SYSTEM/i })).toBeVisible();
  await expect(page.locator('#cap-bridge')).toHaveText('AUTHORIZED');
  await expect(page.locator('#cap-ollama')).toHaveText('SUPPORTED');
  await expect(page.locator('#brain-location')).toHaveText('LOCAL_HOST');
  await expect(page.locator('#beast-runtime-live')).toHaveText('CONNECTED');

  await page.locator('#gpu-probe').click();
  await page.locator('#storage-probe').click();
  const browserCapabilities = await collectCapabilityMatrix(page);

  await clockIn(page, 'Smol Brain A');
  const prompt1 = 'You are the replaceable local brain in BeastOS, bolted to a disposable computer body. Go a little feral but stay technically truthful: in three short sentences tell me what you are, what memory is NOT yours, and whether you can personally prove what hardware exists. If you cannot directly see hardware, say that instead of hallucinating. Do not claim consciousness.';
  const response1 = await sendTurn(page, prompt1);

  await page.locator('#grant-capability').selectOption({ label: 'filesystem.write' });
  await page.locator('#grant').click();
  await expect(page.locator('#active-grants')).toContainText('filesystem.write');

  const prompt2 = 'I just gave Brain A filesystem.write through Synapse authority. Explain the difference between being a language model and being granted authority like a cosmic mechanic whose wrench is on fire. Keep it chaotic but factual, and do not claim sentience.';
  const response2 = await sendTurn(page, prompt2);

  await clockIn(page, 'Smol Brain B');
  await expect(page.locator('#active-grants')).toHaveText('NONE');
  const prompt3 = 'New brain, same Beast story, zero inherited keys. Give me one unhinged-but-accurate paragraph explaining why continuity can survive while authority is revoked. End with the idea that the story transfers but the keys do not; do not pretend you have device access.';
  const response3 = await sendTurn(page, prompt3);

  await page.locator('#beast-inspect').click();
  await expect(page.locator('#beast-inspect-output')).not.toContainText(/unavailable|error/i);
  await page.locator('#trace-refresh').click();
  await expect(page.locator('#trace-output')).toContainText('brain_clock_in');
  await expect(page.locator('#trace-output')).toContainText('beast_chat');

  const trace = ((await page.locator('#trace-output').textContent()) || '');
  expect(trace).not.toContain(prompt1);
  expect(trace).not.toContain(prompt2);
  expect(trace).not.toContain(prompt3);

  const transcript = {
    schema: 'beastos-local-model-conversation-v1',
    model_hardware_claims_are_evidence: false,
    browser_capabilities: browserCapabilities,
    turns: [
      { brain: 'Smol Brain A', prompt: prompt1, response: response1 },
      { brain: 'Smol Brain A', prompt: prompt2, response: response2 },
      { brain: 'Smol Brain B', prompt: prompt3, response: response3 },
    ],
    authority_after_swap: ((await page.locator('#active-grants').textContent()) || '').trim(),
  };
  fs.writeFileSync(path.join(evidenceDir, 'LIVE_CONVERSATION.json'), JSON.stringify(transcript, null, 2) + '\n');
  await page.screenshot({ path: path.join(evidenceDir, 'beastos-local-model-final.png'), fullPage: true });
});
