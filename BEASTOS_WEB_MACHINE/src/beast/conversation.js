import { BridgeClient } from '../authority/client.js';

const bridge = new BridgeClient();
const $ = (id) => document.getElementById(id);

function resultText(response) {
  const result = response?.result;
  if (typeof result === 'string') return result;
  if (result && typeof result === 'object') {
    for (const key of ['response', 'text', 'reply', 'output', 'message']) {
      if (typeof result[key] === 'string' && result[key].trim()) return result[key];
    }
    return JSON.stringify(result, null, 2);
  }
  return JSON.stringify(response ?? null, null, 2);
}

function addTurn(role, text) {
  const transcript = $('beast-transcript');
  const turn = document.createElement('div');
  turn.className = `beast-turn ${role.toLowerCase()}`;
  const label = document.createElement('strong');
  label.textContent = role;
  const body = document.createElement('pre');
  body.textContent = text;
  turn.append(label, body);
  transcript.append(turn);
  transcript.scrollTop = transcript.scrollHeight;
}

async function inspectBeast() {
  const status = $('beast-runtime-live');
  status.textContent = 'CHECKING';
  status.className = 'state permission-required';
  try {
    const { response } = await bridge.request('/v1/beast/inspect');
    status.textContent = 'CONNECTED';
    status.className = 'state supported';
    $('beast-inspect-output').textContent = JSON.stringify(response.result, null, 2);
    return response;
  } catch (error) {
    status.textContent = 'UNAVAILABLE';
    status.className = 'state unavailable';
    $('beast-inspect-output').textContent = error.message;
    return null;
  }
}

async function sendTurn() {
  const input = $('beast-message');
  const button = $('beast-send');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  button.disabled = true;
  addTurn('YOU', text);
  try {
    const payload = await bridge.post('/v1/beast/chat', { text });
    addTurn('BEAST', resultText(payload.result));
    $('beast-runtime-live').textContent = 'CONNECTED';
    $('beast-runtime-live').className = 'state supported';
  } catch (error) {
    addTurn('SYSTEM', `Turn rejected: ${error.message}`);
  } finally {
    button.disabled = false;
    input.focus();
  }
}

function buildConversationPanel() {
  if ($('conversation')) return;
  const machine = $('machine');
  if (!machine) return;
  const panel = document.createElement('section');
  panel.id = 'conversation';
  panel.className = 'panel beast-conversation';
  panel.innerHTML = `
    <div class="section-head">
      <div><p class="eyebrow">ORBIT / BEAST CONTINUITY</p><h2>REAL BEAST RUNTIME EXCHANGE</h2></div>
      <div class="runtime-live">BEAST <b id="beast-runtime-live" class="state">—</b></div>
    </div>
    <p class="note">Turns go through Beast Box v0.6.0 <code>runtime exchange</code>. The browser transcript is ephemeral; Beast owns durable continuity. Synapse owns authority.</p>
    <div id="beast-transcript" class="beast-transcript" aria-live="polite"></div>
    <label>Message to the active brain<textarea id="beast-message" rows="4" maxlength="15000" placeholder="Clock in a brain, then continue the story."></textarea></label>
    <div class="row"><button id="beast-send">SEND THROUGH BEAST</button><button id="beast-inspect" class="secondary">INSPECT CONTINUITY</button></div>
    <pre id="beast-inspect-output">No continuity inspection run.</pre>
  `;
  machine.parentNode.insertBefore(panel, machine);
  $('beast-send').addEventListener('click', sendTurn);
  $('beast-inspect').addEventListener('click', inspectBeast);
  $('beast-message').addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      sendTurn();
    }
  });
  inspectBeast();
}

buildConversationPanel();
