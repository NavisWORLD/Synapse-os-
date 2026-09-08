export const CapabilityState = Object.freeze({
  SUPPORTED: 'SUPPORTED',
  PERMISSION_REQUIRED: 'PERMISSION_REQUIRED',
  AUTHORIZED: 'AUTHORIZED',
  DENIED: 'DENIED',
  UNAVAILABLE: 'UNAVAILABLE',
});

const supported = (condition, permission = false) =>
  condition ? (permission ? CapabilityState.PERMISSION_REQUIRED : CapabilityState.SUPPORTED) : CapabilityState.UNAVAILABLE;

export function detectCapabilities(env = globalThis) {
  const nav = env.navigator ?? {};
  const media = nav.mediaDevices ?? {};
  return {
    camera: supported(typeof media.getUserMedia === 'function', true),
    microphone: supported(typeof media.getUserMedia === 'function', true),
    filesystem: supported(typeof env.showOpenFilePicker === 'function' || typeof env.FileReader === 'function'),
    opfs: supported(typeof nav.storage?.getDirectory === 'function'),
    webgpu: supported(Boolean(nav.gpu)),
    webusb: supported(Boolean(nav.usb)),
    serial: supported(Boolean(nav.serial)),
    bluetooth: supported(Boolean(nav.bluetooth)),
    network: supported('onLine' in nav),
    wasm: supported(typeof env.WebAssembly === 'object'),
    wasmThreads: supported(Boolean(env.crossOriginIsolated && typeof env.SharedArrayBuffer === 'function')),
  };
}

export function wasmSimdAvailable(env = globalThis) {
  if (!env.WebAssembly?.validate) return false;
  const bytes = new Uint8Array([0,97,115,109,1,0,0,0,1,5,1,96,0,1,123,3,2,1,0,10,22,1,20,0,253,12,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,11]);
  try { return env.WebAssembly.validate(bytes); } catch { return false; }
}

export async function probeWebGPU(env = globalThis) {
  const gpu = env.navigator?.gpu;
  if (!gpu) return { state: CapabilityState.UNAVAILABLE, details: null };
  try {
    const adapter = await gpu.requestAdapter();
    if (!adapter) return { state: CapabilityState.UNAVAILABLE, details: null };
    const info = adapter.info ?? {};
    return {
      state: CapabilityState.SUPPORTED,
      details: {
        vendor: info.vendor || 'not reported',
        architecture: info.architecture || 'not reported',
        device: info.device || 'not reported',
        description: info.description || 'not reported',
        features: [...adapter.features].sort(),
      },
    };
  } catch (error) {
    return { state: CapabilityState.DENIED, details: { error: String(error?.message || error) } };
  }
}

export async function probeStorage(env = globalThis) {
  const storage = env.navigator?.storage;
  if (!storage?.estimate) return { state: CapabilityState.UNAVAILABLE };
  const estimate = await storage.estimate();
  return { state: CapabilityState.SUPPORTED, usage: estimate.usage ?? 0, quota: estimate.quota ?? 0 };
}
