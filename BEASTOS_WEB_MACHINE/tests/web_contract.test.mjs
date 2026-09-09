import test from 'node:test';
import assert from 'node:assert/strict';
import { CapabilityState, detectCapabilities, wasmSimdAvailable } from '../src/hardware/capabilities.js';
import { BridgeClient } from '../src/authority/client.js';
import { FileScope, ScopeDescriptions } from '../src/storage/scopes.js';

test('capability detection reports unsupported APIs instead of inventing devices', () => {
  const env = { navigator: { onLine: true }, WebAssembly, FileReader: undefined, crossOriginIsolated: false };
  const caps = detectCapabilities(env);
  assert.equal(caps.camera, CapabilityState.UNAVAILABLE);
  assert.equal(caps.webgpu, CapabilityState.UNAVAILABLE);
  assert.equal(caps.network, CapabilityState.SUPPORTED);
});

test('file upload scope is explicitly temporary', () => {
  assert.equal(FileScope.TEMPORARY_ATTACHMENT, 'TEMPORARY_ATTACHMENT');
  assert.match(ScopeDescriptions[FileScope.TEMPORARY_ATTACHMENT], /never makes a file permanent/i);
});

test('bridge client rejects non API paths before network access', async () => {
  const client = new BridgeClient();
  await assert.rejects(() => client.request('/shell'), /must start with \/v1\//);
});

test('SIMD detector fails closed without WebAssembly validation', () => {
  assert.equal(wasmSimdAvailable({ WebAssembly: null }), false);
});
