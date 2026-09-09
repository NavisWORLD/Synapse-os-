import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseURL = process.env.BEASTOS_BASE_URL || 'http://127.0.0.1:8790';
const evidenceDir = path.resolve(process.env.BEASTOS_EVIDENCE_DIR || 'demo-evidence-5min');
const modelLabel = 'qwen2.5:0.5b';
await fs.mkdir(evidenceDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1080 },
  permissions: [],
  recordVideo: { dir: path.join(evidenceDir, 'raw-video'), size: { width: 1440, height: 1080 } },
});
const page = await context.newPage();
const consoleLines = [];
const turns = [];
page.on('console', (msg) => consoleLines.push(`[${new Date().toISOString()}] ${msg.type()}: ${msg.text()}`));

async function linger(ms = 7000) {
  await page.waitForTimeout(ms);
}

async function clockIn(name) {
  await page.locator('#brain-name').fill(name);
  await page.locator('#brain-clock').click();
  await page.waitForFunction((n) => document.querySelector('#active-brain')?.textContent?.includes(n), name, { timeout: 60000 });
  await linger(3500);
}

async function send(text, lingerMs = 8500) {
  const before = await page.locator('.beast-turn.beast').count();
  await page.locator('#conversation').scrollIntoViewIfNeeded();
  await page.locator('#beast-message').fill(text);
  await linger(1200);
  await page.locator('#beast-send').click();
  await page.waitForFunction(
    (n) => document.querySelectorAll('.beast-turn.beast').length === n + 1,
    before,
    { timeout: 180000 },
  );
  const response = await page.locator('.beast-turn.beast').nth(before).locator('pre').innerText();
  turns.push({ timestamp: new Date().toISOString(), prompt: text, response });
  await page.locator('.beast-turn.beast').nth(before).scrollIntoViewIfNeeded();
  await linger(lingerMs);
  return response;
}

await page.goto(baseURL, { waitUntil: 'networkidle', timeout: 120000 });
await page.locator('#cap-bridge').waitFor({ state: 'visible' });
await page.waitForFunction(() => document.querySelector('#cap-bridge')?.textContent !== '—', null, { timeout: 60000 });
await linger(7000);

await page.locator('#devices').scrollIntoViewIfNeeded();
await linger(6000);
await clockIn('Demo Brain A');

for (const [buttonId, capId] of [['#camera-start', '#cap-camera'], ['#mic-start', '#cap-mic']]) {
  const beforeState = (await page.locator(capId).innerText()).trim();
  await page.locator(buttonId).click();
  await linger(1600);
  const afterState = (await page.locator(capId).innerText()).trim();
  consoleLines.push(`[${new Date().toISOString()}] media-probe ${capId} ${beforeState} -> ${afterState}`);
}

const capIds = ['camera', 'mic', 'webgpu', 'files', 'opfs', 'usb', 'serial', 'bluetooth', 'network', 'wasm', 'wasm-simd', 'wasm-threads', 'bridge', 'ollama', 'beast', 'vm'];
const capabilities = {};
for (const id of capIds) capabilities[id] = (await page.locator(`#cap-${id}`).innerText()).trim();

await page.locator('#gpu-probe').click();
await linger(2500);
const gpuDetails = await page.locator('#gpu-details').innerText();
await page.locator('#storage-probe').click();
await linger(2000);
const storageDetails = await page.locator('#storage-details').innerText();
await page.locator('#conversation').scrollIntoViewIfNeeded();

await send(`We just booted Synapse OS and opened BeastOS Web. You are the real local model ${modelLabel} behind Beast Box v0.6.0. Introduce yourself as a replaceable model in this architecture. Be factual: model is not memory, state, provenance, authority, or the whole system. Keep it conversational, no consciousness claims.`);

const capSummary = Object.entries(capabilities).map(([key, value]) => `${key}=${value}`).join(', ');
await send(`Here are measurements from the actual browser session: ${capSummary}. Explain what these states mean in plain English. Separate detected capability from granted authority, and do not invent hardware that is not in the measurements.`);

await send('Okay, now talk to me like an engineer at the console. Why is it useful that Beast Box keeps continuity outside the replaceable model? Give me a concrete example involving swapping one local model for another while keeping the story and provenance.');

await page.locator('#grant-capability').selectOption({ label: 'filesystem.write' });
await page.locator('#grant').click();
await page.waitForFunction(() => document.querySelector('#active-grants')?.textContent?.includes('filesystem.write'));
const grantsBeforeSwap = (await page.locator('#active-grants').innerText()).trim();
await linger(5000);

await send('Brain A now has an explicit filesystem.write grant. Explain why that key belongs to Synapse authority rather than to you, the model, and why it should not automatically follow a future brain swap.');

await clockIn('Demo Brain B');
const grantsAfterSwap = (await page.locator('#active-grants').innerText()).trim();
await linger(5500);

await send('The brain label just changed to Demo Brain B. The old filesystem grant is gone, but the Beast continuity substrate is still present. Tell me what changed and what did not change. Keep the distinction between story/state and authority crystal clear.');

await send('Now have a little fun with it. Describe this setup as a cosmic machine in one paragraph, but stay technically accurate: browser cockpit, Synapse host, Beast continuity, replaceable model, disposable VM body, scoped keys. No fake sentience or magic.');

await send('Suppose I destroy a disposable QEMU body after a task. What should survive, what should die with the body, and what must require fresh authorization next time? Answer like a security-minded systems engineer.');

await send('Final turn. Summarize what this demo actually proved in a few short lines, without exaggerating beyond the measurements and runtime receipts. End exactly with: SWAP THE BRAIN. KEEP THE STORY.', 12000);

await page.locator('#beast-inspect').click();
await linger(2500);
const inspectAfter = await page.locator('#beast-inspect-output').innerText();
await page.locator('#trace-refresh').click();
await linger(3000);
const trace = await page.locator('#trace-output').innerText();
await page.locator('#trace').scrollIntoViewIfNeeded();
await linger(9000);

await page.screenshot({ path: path.join(evidenceDir, 'beastos-5min-final.png'), fullPage: true });
await fs.writeFile(path.join(evidenceDir, 'conversation-5min.json'), JSON.stringify({
  schema: 'beastos-live-conversation-5min-v1',
  baseURL,
  model: modelLabel,
  turns,
  grantsBeforeSwap,
  grantsAfterSwap,
  inspectAfter,
}, null, 2));
await fs.writeFile(path.join(evidenceDir, 'browser-capabilities-5min.json'), JSON.stringify({
  schema: 'beastos-browser-capabilities-v1',
  measured_at: new Date().toISOString(),
  capabilities,
  gpuDetails,
  storageDetails,
}, null, 2));
await fs.writeFile(path.join(evidenceDir, 'synapse-trace-5min.txt'), trace + '\n');
await fs.writeFile(path.join(evidenceDir, 'browser-console-5min.log'), consoleLines.join('\n') + '\n');

const video = page.video();
await page.close();
await context.close();
if (video) {
  const rawPath = await video.path();
  await fs.copyFile(rawPath, path.join(evidenceDir, 'beastos-conversation-5min.webm'));
}
await browser.close();
