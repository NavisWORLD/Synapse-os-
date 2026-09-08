export class BridgeClient {
  constructor(base = '') { this.base = base.replace(/\/$/, ''); }

  async request(path, options = {}) {
    if (!path.startsWith('/v1/')) throw new Error('bridge API path must start with /v1/');
    const response = await fetch(this.base + path, {
      credentials: 'same-origin',
      cache: 'no-store',
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    const payload = await response.json();
    if (!response.ok || payload.ok === false) {
      throw new Error(payload?.error?.message || payload?.error?.code || `HTTP ${response.status}`);
    }
    return payload;
  }

  getStatus() { return this.request('/v1/status'); }
  getTrace() { return this.request('/v1/provenance'); }
  post(path, data = {}) { return this.request(path, { method: 'POST', body: JSON.stringify(data) }); }
}
