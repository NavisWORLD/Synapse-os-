# Synapse Phone Bootstrap Design

## Goal

Give a phone a tiny browser control surface that can identify a directly reachable Synapse OS laptop, exchange an authenticated “hey, I’m here” handshake, and start a fixed-purpose COSMOS GitHub install/service-activation job without giving the browser arbitrary shell or disk-write capability.

## Architecture

The laptop runs a Python-standard-library HTTP daemon on port `8787`. It serves the phone HTML and a versioned `/v1` JSON API. The phone page can run from the laptop itself or from a saved local copy and communicates over any routed trusted local link, including a USB networking/tethering bridge.

The API uses a random pairing token. `GET /v1/health` is public so the page can discover that the daemon is alive. Device details, hello, install and install status require the token. There are no generic command, raw-disk, wipe, firmware or reimage endpoints.

## Device probe

`GET /v1/device` returns hostname, OS/kernel, architecture, processor, logical CPU count, RAM, root filesystem capacity/free space, battery percentage when Linux exposes it, local IPv4 addresses when the `ip` tool exists, and reachability of the established COSMOS service ports.

## COSMOS install

`POST /v1/install/start` starts one background job. The server-side configuration fixes the Git repository and installation root. Request JSON cannot inject a repository URL or shell command.

The default repository is `https://github.com/NavisWORLD/Cosmos.git`, branch `main`.

If the checkout does not exist, it is shallow-cloned. If it exists and is clean, only a fast-forward pull is allowed. If it contains local modifications, the checkout is preserved and is not reset.

When activation is enabled, Docker Compose is preferred when a compose file exists. Otherwise a repository `Dockerfile` is built and started as a named restartable container. Existing containers are started rather than deleted/recreated. If no supported activation path exists, source installation remains intact and the API reports the activation failure.

## OS integration

Synapse OS includes:

- `src/synapse/phone_bootstrap.py`
- `/usr/local/bin/synapse-phone-bootstrap`
- a global per-user systemd unit so the daemon runs as the signed-in user rather than root
- `/usr/share/synapse/phone-bootstrap.html`

A fresh token is written under the user runtime directory on service start. The install root is `%h/COSMOS`.

## Testing

Unit tests cover the device payload shape, disabled-install guard, protection of an existing non-Git install directory, and explicit UI path resolution. Syntax checks cover Python and the shell wrapper. The HTML has a smoke check for the required install and handshake routes.
