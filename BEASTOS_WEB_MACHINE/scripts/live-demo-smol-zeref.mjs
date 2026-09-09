import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const baseURL = process.env.BEASTOS_BASE_URL || 'http://127.0.0.1:8790';
const providerURL = process.env.BEASTOS_LINEAGE_PROVIDER_URL || 'http://127.0.0.1:11436';
const evidenceDir = path.resolve(process.env.BEASTOS_EVIDENCE_DIR || 'demo-evidence-smol-zeref');
await fs.mkdir(evidenceDir, { recursive: true });

async function providerGet(route) {
  const response = await fetch(providerURL + route);
  if (!response.ok) throw new Error(`lineage provider ${route} failed: ${response.status}`);
  return await response.json();
}

async function providerPost(route, payload) {
  const response = await fetch(providerURL + route, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`lineage provider ${route} failed: ${response.status}`);
  return await response.json();
}

const statusBefore = await providerGet('/demo/status');
if (statusBefore.active !== 'smol') throw new Error('lineage provider must start on exact Smol');

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 1080 },
  permissions: [],
  recordVideo: { dir: path.join(evidenceDir, 'raw-video'), size: { width: 1440, height: 1080 } },
});
const page = await context.newPage();
const turns = [];
const consoleLines = [];
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

async function send(brain, text, lingerMs = 8500) {
  const before = await page.locator('.beast-turn.beast').count();
  await page.locator('#conversation').scrollIntoViewIfNeeded();
  await page.locator('#beast-message').fill(text);
  await linger(1000);
  await page.locator('#beast-send').click();
  await page.waitForFunction(
    (n) => document.querySelectorAll('.beast-turn.beast').length === n + 1,
    before,
    { timeout: 240000 },
  );
  const response = await page.locator('.beast-turn.beast').nth(before).locator('pre').innerText();
  turns.push({ timestamp: new Date().toISOString(), brain, prompt: text, response });
  await page.locator('.beast-turn.beast').nth(before).scrollIntoViewIfNeeded();
  await linger(lingerMs);
  return response;
}

await page.goto(baseURL, { waitUntil: 'networkidle', timeout: 120000 });
await page.locator('#cap-bridge').waitFor({ state: 'visible' });
await page.waitForFunction(() => document.querySelector('#cap-bridge')?.textContent !== '—', null, { timeout: 60000 });
await linger(6500);

await page.locator('#devices').scrollIntoViewIfNeeded();
await linger(5000);
const capIds = ['camera', 'mic', 'webgpu', 'files', 'opfs', 'usb', 'serial', 'bluetooth', 'network', 'wasm', 'bridge', 'beast', 'vm'];
const capabilities = {};
for (const id of capIds) capabilities[id] = (await page.locator(`#cap-${id}`).innerText()).trim();
await page.locator('#gpu-probe').click();
await linger(1800);
const gpuDetails = await page.locator('#gpu-details').innerText();

await clockIn('Behom Smol / SmolLM2-135M');
await send(
  'smol',
  'Alright tiny beast, Cory fired Qwen. You are the exact frozen SmolLM2-135M brain behind Beast right now. Roast this ridiculous OS experiment a little, but only claim what you can actually infer from the prompt and runtime.',
  9000,
);
await send(
  'smol',
  `The browser measured these states: ${Object.entries(capabilities).map(([k, v]) => `${k}=${v}`).join(', ')}. Talk trash about the unsupported parts, then tell me the difference between detected capability and granted authority. Do not invent hardware.`,
  9000,
);
await send(
  'smol',
  'Be honest: model is not memory, state, provenance, authority, or the whole system. What is the dumbest false claim somebody could make after seeing this demo? Keep it short and rude-funny, not mystical.',
  9000,
);

await page.locator('#grant-capability').selectOption({ label: 'filesystem.write' });
await page.locator('#grant').click();
await page.waitForFunction(() => document.querySelector('#active-grants')?.textContent?.includes('filesystem.write'));
const grantsBeforeSwap = (await page.locator('#active-grants').innerText()).trim();
await linger(4500);
await send(
  'smol',
  'You temporarily have a filesystem.write grant from Synapse authority. I am about to replace your brain with Zeref. Give Zeref one line of trash talk before I pull the plug on your grant.',
  10000,
);

const providerSwap = await providerPost('/demo/brain', { brain: 'zeref' });
if (providerSwap.previous !== 'smol' || providerSwap.active !== 'zeref' || providerSwap.authority_transferred !== false) {
  throw new Error(`unexpected provider swap receipt: ${JSON.stringify(providerSwap)}`);
}
await clockIn('Zeref / exact 454f3017');
const grantsAfterSwap = (await page.locator('#active-grants').innerText()).trim();
if (grantsAfterSwap !== 'NONE') throw new Error(`authority survived brain swap: ${grantsAfterSwap}`);
await linger(6000);

await send(
  'zeref',
  'Zeref, Smol says you are inheriting a chair, not a kingdom. You are now the exact frozen checkpoint. Respond however your actual weights respond. No roleplay requirement and no consciousness claim.',
  10000,
);
await send(
  'zeref',
  'The Beast continuity substrate stayed in place across the swap, but the old filesystem write grant is gone. Say what you can about that separation from the text you received. Raw answer is fine.',
  10000,
);
await send(
  'zeref',
  'Cory wants receipts, not mythology. What can this runtime establish right now, and what can you not directly see? If your tiny character model gets weird, get weird honestly.',
  10000,
);
await send(
  'zeref',
  'Final round. Roast Smol, roast this cosmic browser machine, and give one final line for the demo. Do not claim sentience, a soul, biological life, or magical hardware access.',
  12000,
);

await page.locator('#beast-inspect').click();
await linger(2500);
const inspectAfter = await page.locator('#beast-inspect-output').innerText();
await page.locator('#trace-refresh').click();
await linger(3500);
const trace = await page.locator('#trace-output').innerText();
const statusAfterTurns = await providerGet('/demo/status');

await page.locator('#trace').scrollIntoViewIfNeeded();
await linger(8000);
await page.screenshot({ path: path.join(evidenceDir, 'smol-zeref-final.png'), fullPage: true });

const closeReceipt = await providerPost('/demo/close', {});
if (closeReceipt.smol?.parameter_drift !== false || closeReceipt.zeref?.parameter_drift !== false) {
  throw new Error(`frozen parameter drift detected: ${JSON.stringify(closeReceipt)}`);
}

await fs.writeFile(path.join(evidenceDir, 'smol-zeref-conversation.json'), JSON.stringify({
  schema: 'beastos-smol-zeref-live-conversation-v1',
  baseURL,
  providerURL,
  turns,
  grantsBeforeSwap,
  grantsAfterSwap,
  providerSwap,
  providerStatusBefore: statusBefore,
  providerStatusAfterTurns: statusAfterTurns,
  closeReceipt,
  inspectAfter,
}, null, 2));
await fs.writeFile(path.join(evidenceDir, 'browser-capabilities.json'), JSON.stringify({
  schema: 'beastos-browser-capabilities-v1',
  measured_at: new Date().toISOString(),
  capabilities,
  gpuDetails,
}, null, 2));
await fs.writeFile(path.join(evidenceDir, 'synapse-trace.txt'), trace + '\n');
await fs.writeFile(path.join(evidenceDir, 'browser-console.log'), consoleLines.join('\n') + '\n');

const video = page.video();
await page.close();
await context.close();
if (video) {
  const rawPath = await video.path();
  await fs.copyFile(rawPath, path.join(evidenceDir, 'smol-zeref-conversation.webm'));
}
await browser.close();
