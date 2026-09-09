import { BridgeClient } from '../authority/client.js';
import { CapabilityState, detectCapabilities, probeStorage, probeWebGPU, wasmSimdAvailable } from '../hardware/capabilities.js';
import { FileScope, ScopeDescriptions } from '../storage/scopes.js';

const bridge = new BridgeClient();
const streams = new Set();
const $ = (id) => document.getElementById(id);
const stateClass = (value) => `state ${String(value).toLowerCase().replaceAll('_', '-')}`;

function setText(id, text) { const node = $(id); if (node) node.textContent = text; }
function setState(id, value) { const node = $(id); if (!node) return; node.textContent = value; node.className = stateClass(value); }
function log(message) {
  const out = $('event-log');
  const line = document.createElement('div');
  line.textContent = `${new Date().toLocaleTimeString()}  ${message}`;
  out.prepend(line);
  while (out.children.length > 40) out.lastElementChild?.remove();
}

async function refreshBridge() {
  try {
    const { status } = await bridge.getStatus();
    setState('cap-bridge', 'AUTHORIZED');
    setState('cap-beast', status.beast.connected ? 'AUTHORIZED' : 'UNAVAILABLE');
    setState('cap-ollama', status.ollama.connected ? 'SUPPORTED' : 'UNAVAILABLE');
    setState('cap-vm', status.machine.state === 'UNAVAILABLE' ? 'UNAVAILABLE' : 'SUPPORTED');
    setText('active-brain', status.active_brain || 'NO BRAIN CLOCKED IN');
    setText('brain-location', status.beast.provider_location);
    setText('beast-version', `${status.beast.release} · ${status.beast.commit.slice(0, 12)} · prerelease ${status.beast.prerelease}`);
    setText('active-grants', status.grants.length ? status.grants.join(', ') : 'NONE');
    renderMachine(status.machine);
    return status;
  } catch (error) {
    for (const id of ['cap-bridge','cap-beast','cap-ollama','cap-vm']) setState(id, 'UNAVAILABLE');
    log(`Bridge offline: ${error.message}`);
    return null;
  }
}

function renderMachine(machine) {
  setText('machine-state', machine.state || 'UNAVAILABLE');
  setText('machine-engine', machine.engine || 'NOT ESTABLISHED');
  setText('machine-cpu', machine.cpus ? `${machine.cpus} vCPU` : '—');
  setText('machine-memory', machine.memory_mb ? `${machine.memory_mb} MiB` : '—');
  setText('machine-network', machine.network_mode || 'none');
  setText('machine-reason', machine.reason || 'Disposable guest; host authority is not inherited.');
}

function renderCapabilities() {
  const caps = detectCapabilities();
  const ids = {camera:'cap-camera',microphone:'cap-mic',filesystem:'cap-files',opfs:'cap-opfs',webgpu:'cap-webgpu',webusb:'cap-usb',serial:'cap-serial',bluetooth:'cap-bluetooth',network:'cap-network',wasm:'cap-wasm',wasmThreads:'cap-wasm-threads'};
  for (const [key, value] of Object.entries(caps)) setState(ids[key], value);
  setState('cap-wasm-simd', wasmSimdAvailable() ? CapabilityState.SUPPORTED : CapabilityState.UNAVAILABLE);
  setText('browser-network', navigator.onLine ? 'ONLINE · STATUS ONLY' : 'OFFLINE');
  window.addEventListener('online', () => setText('browser-network', 'ONLINE · STATUS ONLY'));
  window.addEventListener('offline', () => setText('browser-network', 'OFFLINE'));
}

async function requestMedia(kind) {
  if (!navigator.mediaDevices?.getUserMedia) { setState(kind === 'video' ? 'cap-camera' : 'cap-mic', 'UNAVAILABLE'); return; }
  const id = kind === 'video' ? 'cap-camera' : 'cap-mic';
  try {
    const stream = await navigator.mediaDevices.getUserMedia(kind === 'video' ? { video: true } : { audio: true });
    streams.add(stream); setState(id, 'AUTHORIZED');
    if (kind === 'video') { const preview = $('camera-preview'); preview.srcObject = stream; preview.hidden = false; }
    if (kind === 'audio') startMeter(stream);
    log(`${kind === 'video' ? 'Camera' : 'Microphone'} authorized by browser user gesture.`);
  } catch (error) { setState(id, 'DENIED'); log(`${kind} denied: ${error.name || error.message}`); }
}

function startMeter(stream) {
  try {
    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser(); source.connect(analyser); analyser.fftSize = 256;
    const data = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      if (![...stream.getTracks()].some((track) => track.readyState === 'live')) { context.close(); return; }
      analyser.getByteFrequencyData(data);
      $('mic-level').value = Math.min(100, Math.round(data.reduce((a, b) => a + b, 0) / data.length));
      requestAnimationFrame(tick);
    };
    tick();
  } catch { setText('mic-note', 'Meter unavailable; microphone stream is still browser-controlled.'); }
}

function stopMedia() {
  for (const stream of streams) for (const track of stream.getTracks()) track.stop();
  streams.clear();
  const preview = $('camera-preview'); preview.srcObject = null; preview.hidden = true;
  $('mic-level').value = 0;
  const caps = detectCapabilities(); setState('cap-camera', caps.camera); setState('cap-mic', caps.microphone);
}

async function postAndRefresh(path, data, note) {
  try { await bridge.post(path, data); if (note) log(note); await refreshBridge(); }
  catch (error) { log(`${note || path} failed: ${error.message}`); throw error; }
}

function wireActions() {
  $('camera-start').addEventListener('click', () => requestMedia('video'));
  $('camera-stop').addEventListener('click', () => { stopMedia(); log('Browser media streams stopped.'); });
  $('mic-start').addEventListener('click', () => requestMedia('audio'));
  $('mic-stop').addEventListener('click', () => { stopMedia(); log('Browser media streams stopped.'); });
  $('brain-clock').addEventListener('click', async () => {
    stopMedia();
    const brain = $('brain-name').value.trim();
    if (!brain) { log('Brain identifier required.'); return; }
    await postAndRefresh('/v1/brain/clock-in', { brain }, `Clocked in ${brain}; prior brain authority revoked.`);
  });
  $('grant').addEventListener('click', () => postAndRefresh('/v1/authority/grant', { capability: $('grant-capability').value }, 'Authority granted.'));
  $('revoke').addEventListener('click', () => postAndRefresh('/v1/authority/revoke', { capability: $('grant-capability').value }, 'Authority revoked.'));
  $('privacy-stop').addEventListener('click', async () => { stopMedia(); await postAndRefresh('/v1/privacy/stop', {}, 'MASTER PRIVACY STOP executed.'); });
  $('machine-create').addEventListener('click', () => postAndRefresh('/v1/machine/create', {memory_mb:Number($('machine-memory-input').value),cpus:Number($('machine-cpu-input').value),network_mode:$('machine-network-input').value}, 'Disposable Beast Machine create requested.'));
  $('machine-destroy').addEventListener('click', () => postAndRefresh('/v1/machine/destroy', {}, 'Disposable Beast Machine destroy requested.'));
  $('gpu-probe').addEventListener('click', async () => { const result = await probeWebGPU(); setState('cap-webgpu', result.state); setText('gpu-details', result.details ? JSON.stringify(result.details, null, 2) : 'No WebGPU adapter.'); });
  $('storage-probe').addEventListener('click', async () => { const result = await probeStorage(); setText('storage-details', result.quota ? `${(result.usage / 2**20).toFixed(1)} MiB used / ${(result.quota / 2**20).toFixed(1)} MiB quota` : result.state); });
  $('trace-refresh').addEventListener('click', async () => { try { const { records } = await bridge.getTrace(); $('trace-output').textContent = JSON.stringify(records.slice(-20), null, 2); } catch (error) { $('trace-output').textContent = error.message; } });
  $('file-picker').addEventListener('change', (event) => {
    const list = $('file-list'); list.replaceChildren();
    for (const file of event.target.files) { const item = document.createElement('li'); item.textContent = `${file.name} · ${file.size} bytes · ${FileScope.TEMPORARY_ATTACHMENT}`; list.append(item); }
    log(`${event.target.files.length} file(s) staged as TEMPORARY_ATTACHMENT; no persistence implied.`);
  });
}

function renderScopes() {
  const out = $('scope-list');
  for (const [scope, description] of Object.entries(ScopeDescriptions)) {
    const node = document.createElement('div'); node.className = 'scope-card';
    const title = document.createElement('strong'); title.textContent = scope;
    const body = document.createElement('span'); body.textContent = description;
    node.append(title, body); out.append(node);
  }
}

function registerPWA() {
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch((error) => log(`Service worker unavailable: ${error.message}`));
  let deferred;
  window.addEventListener('beforeinstallprompt', (event) => { event.preventDefault(); deferred = event; $('install-pwa').hidden = false; });
  $('install-pwa').addEventListener('click', async () => { if (!deferred) return; deferred.prompt(); await deferred.userChoice; deferred = null; $('install-pwa').hidden = true; });
}

renderCapabilities(); renderScopes(); wireActions(); registerPWA(); refreshBridge();
