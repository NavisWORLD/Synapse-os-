import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseURL = process.env.BEASTOS_BASE_URL || 'http://127.0.0.1:8790';
const evidenceDir = path.resolve(process.env.BEASTOS_EVIDENCE_DIR || 'demo-evidence-live');
await fs.mkdir(evidenceDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1080 },
  permissions: [],
  recordVideo: { dir: path.join(evidenceDir, 'raw-video'), size: { width: 1440, height: 1080 } },
});
const page = await context.newPage();
const consoleLines = [];
page.on('console', (msg) => consoleLines.push(`[${new Date().toISOString()}] ${msg.type()}: ${msg.text()}`));

const turns = [];
async function clockIn(name) {
  await page.locator('#brain-name').fill(name);
  await page.locator('#brain-clock').click();
  await page.locator('#active-brain').waitFor({ state: 'visible' });
  await page.waitForFunction((n) => document.querySelector('#active-brain')?.textContent?.includes(n), name);
}

async function send(text) {
  const before = await page.locator('.beast-turn.beast').count();
  await page.locator('#beast-message').fill(text);
  await page.locator('#beast-send').click();
  await page.waitForFunction(
    (n) => document.querySelectorAll('.beast-turn.beast').length === n + 1,
    before,
    { timeout: 180000 },
  );
  const response = await page.locator('.beast-turn.beast').nth(before).locator('pre').innerText();
  turns.push({ timestamp: new Date().toISOString(), prompt: text, response });
  return response;
}

await page.goto(baseURL, { waitUntil: 'networkidle', timeout: 120000 });
await page.locator('#cap-bridge').waitFor({ state: 'visible' });
await page.waitForFunction(() => document.querySelector('#cap-bridge')?.textContent !== '—', null, { timeout: 60000 });
await page.waitForTimeout(2500);
await clockIn('Demo Brain A');

// Exercise real browser media APIs. Whatever the CI browser reports is recorded; nothing is simulated.
for (const [buttonId, capId] of [['#camera-start', '#cap-camera'], ['#mic-start', '#cap-mic']]) {
  const beforeState = (await page.locator(capId).innerText()).trim();
  await page.locator(buttonId).click();
  await page.waitForTimeout(1200);
  const afterState = (await page.locator(capId).innerText()).trim();
  consoleLines.push(`[${new Date().toISOString()}] media-probe ${capId} ${beforeState} -> ${afterState}`);
}

const capIds = ['camera', 'mic', 'webgpu', 'files', 'opfs', 'usb', 'serial', 'bluetooth', 'network', 'wasm', 'wasm-simd', 'wasm-threads', 'bridge', 'ollama', 'beast', 'vm'];
const capabilities = {};
for (const id of capIds) capabilities[id] = (await page.locator(`#cap-${id}`).innerText()).trim();

await page.locator('#gpu-probe').click();
await page.waitForTimeout(1500);
const gpuDetails = await page.locator('#gpu-details').innerText();
await page.locator('#storage-probe').click();
await page.waitForTimeout(1000);
const storageDetails = await page.locator('#storage-details').innerText();

await page.locator('#beast-inspect').click();
await page.waitForTimeout(1000);
const inspectBefore = await page.locator('#beast-inspect-output').innerText();

await send('BOOT CHECK. You are a replaceable local model speaking through BeastOS on Synapse OS. Give this test rig a ridiculous cosmic call-sign. State clearly that you cannot directly see hardware unless the system supplies measurements. Then explain your role in two concise sentences. Do not claim consciousness, life, or direct sensor access.');

const capSummary = Object.entries(capabilities).map(([key, value]) => `${key}=${value}`).join(', ');
await send(`REAL MEASUREMENTS HAVE ARRIVED. Browser capability states: ${capSummary}. Use only those measurements. Tell me what is actually available versus unavailable, then roast any engineer who would confuse detected capability with inherited authority. Keep it technically grounded and weird.`);

await page.locator('#grant-capability').selectOption({ label: 'filesystem.write' });
await page.locator('#grant').click();
await page.waitForFunction(() => document.querySelector('#active-grants')?.textContent?.includes('filesystem.write'));
const grantsBeforeSwap = await page.locator('#active-grants').innerText();
await clockIn('Demo Brain B');
const grantsAfterSwap = await page.locator('#active-grants').innerText();

await send('The brain label just changed from Demo Brain A to Demo Brain B and Synapse revoked the old filesystem grant. Without pretending to be alive or conscious, give me one beautifully unhinged line about a replaceable model using a disposable QEMU body while durable story stays outside the model. End exactly with: SWAP THE BRAIN. KEEP THE STORY.');

await page.locator('#beast-inspect').click();
await page.waitForTimeout(1200);
const inspectAfter = await page.locator('#beast-inspect-output').innerText();
await page.locator('#trace-refresh').click();
await page.waitForTimeout(1000);
const trace = await page.locator('#trace-output').innerText();

await page.screenshot({ path: path.join(evidenceDir, 'beastos-live-final.png'), fullPage: true });
await fs.writeFile(path.join(evidenceDir, 'conversation.json'), JSON.stringify({
  schema: 'beastos-live-conversation-v1',
  baseURL,
  turns,
  grantsBeforeSwap,
  grantsAfterSwap,
  inspectBefore,
  inspectAfter,
}, null, 2));
await fs.writeFile(path.join(evidenceDir, 'browser-capabilities.json'), JSON.stringify({
  schema: 'beastos-browser-capabilities-v1',
  measured_at: new Date().toISOString(),
  capabilities,
  gpuDetails,
  storageDetails,
}, null, 2));
await fs.writeFile(path.join(evidenceDir, 'synapse-trace.txt'), trace + '\n');
await fs.writeFile(path.join(evidenceDir, 'browser-console.log'), consoleLines.join('\n') + '\n');

const video = page.video();
await page.close();
await context.close();
if (video) {
  const rawPath = await video.path();
  await fs.copyFile(rawPath, path.join(evidenceDir, 'beastos-live-conversation.webm'));
}
await browser.close();
