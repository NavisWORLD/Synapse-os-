# PHONE BOOTSTRAP

The implementation lives in [`phone-bootstrap/`](phone-bootstrap/) and `src/synapse/phone_bootstrap.py`.

**Flow:** phone HTML → authenticated local API on port 8787 → laptop hardware probe → COSMOS GitHub checkout → supported service activation → status returned to the phone.

Start manually with:

```bash
PYTHONPATH=src python3 -m synapse.phone_bootstrap --listen 0.0.0.0 --port 8787 --allow-install --activate --install-root "$HOME/COSMOS"
```

See [`phone-bootstrap/README.md`](phone-bootstrap/README.md) for the complete usage and security model.
