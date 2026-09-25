#!/usr/bin/env python3
"""One-turn, credential-safe verification of a guest-initiated local SmolLM conversation.

Never sends a model turn itself. The one visible turn must be initiated in the
Synapse guest browser; this host-side tool only checks provider and continuity.
"""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import sys
import time
from urllib import request, error

SITE = "https://www.beastboxcosmos.xyz"
COOKIE_FILE = Path("/tmp/synapse-smol-demo-session.cookies")
STATE_FILE = Path("/tmp/synapse-smol-demo-status.json")
TIMEOUT = 25


def ask(path, payload=None, jar=None):
    opener = request.build_opener(request.HTTPCookieProcessor(jar))
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = request.Request(SITE + path, data=data, headers=headers, method="POST" if data else "GET")
    with opener.open(req, timeout=TIMEOUT) as res:
        return json.load(res)


def selected_model(response):
    """Use host-attested installed local option, not a provider display label."""
    active = response.get("active") if isinstance(response, dict) else None
    choices = response.get("choices") if isinstance(response, dict) else None
    if not isinstance(active, dict) or not isinstance(choices, list):
        raise RuntimeError("No authenticated model catalog was returned.")
    matching = [
        c for c in choices if isinstance(c, dict)
        and c.get("choice") == "local"
        and c.get("kind") == "local"
        and c.get("configured") is True
        and c.get("requires_spend_approval") is False
        and c.get("readiness") == "LOCAL_WEIGHTS_AND_LOOPBACK_VERIFIED"
    ]
    if not matching:
        raise RuntimeError("No installed and verified local SmolLM provider is available.")
    model = str(matching[0].get("model") or "")
    if not model or active.get("remote") is not False or active.get("model") != model:
        raise RuntimeError("The verified local model is not selected.")
    return model, "verified_local"



def turns_from(response):
    turns = response.get("turns") if isinstance(response, dict) else None
    if not isinstance(turns, list):
        raise RuntimeError("Authenticated conversation endpoint did not return actual turns.")
    return turns


def role_of(turn):
    return str(turn.get("kind") or turn.get("role") or "").lower()


def text_of(turn):
    return str(turn.get("text") or turn.get("content") or "")


def preflight():
    password = os.environ.get("DEMO_PASSWORD", "")
    if not password:
        raise RuntimeError("BEASTBOX_DEMO_PASSWORD missing. Store in private GitHub Actions secrets.")
    jar = http.cookiejar.MozillaCookieJar(str(COOKIE_FILE))
    # Do not persist the entered password, a token, session response or private turns.
    ask("/api/session", {"password": password}, jar)
    status = ask("/api/status", jar=jar)
    if status.get("backendReachable") is not True:
        raise RuntimeError("Website is logged in, but its backend is not confirmed reachable.")
    catalog = ask("/api/bridge/models", jar=jar)
    active = catalog.get("active") if isinstance(catalog, dict) else {}
    choices = catalog.get("choices") if isinstance(catalog, dict) else []
    verified_local = any(
        isinstance(c, dict) and c.get("choice") == "local"
        and c.get("kind") == "local" and c.get("configured") is True
        and c.get("readiness") == "LOCAL_WEIGHTS_AND_LOOPBACK_VERIFIED"
        and c.get("requires_spend_approval") is False for c in choices
    )
    if not verified_local:
        raise RuntimeError("Local SmolLM is not verified/available: remote models will not be called.")
    if not isinstance(active, dict) or active.get("remote") is not False or active.get("model") != next(c["model"] for c in choices if isinstance(c, dict) and c.get("choice") == "local" and c.get("readiness") == "LOCAL_WEIGHTS_AND_LOOPBACK_VERIFIED"):
        # The user requested the existing Smol model as an acceptable choice;
        # select it through the same authenticated owner-only endpoint as Brain Bay.
        # This handoff revokes model/tool authority but never invokes paid inference.
        ask("/api/bridge/models", {"choice": "local"}, jar=jar)
    model, kind = selected_model(ask("/api/bridge/models", jar=jar))
    turns = turns_from(ask("/api/bridge/conversation", jar=jar))
    marker = "SYNAPSE-NESTED-" + os.environ["GITHUB_RUN_ID"]
    if any(marker in text_of(t) for t in turns):
        raise RuntimeError("This Actions run already submitted its unique demo turn; refusing duplicate inference.")
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    jar.save(ignore_discard=True, ignore_expires=True)
    os.chmod(COOKIE_FILE, 0o600)
    STATE_FILE.write_text(json.dumps({"marker": marker, "model": model, "kind": kind, "before_turns": len(turns)}))
    os.chmod(STATE_FILE, 0o600)
    # The only preflight output is a non-secret readiness receipt.
    print(f"READY: authenticated website, verified local model {model}, {len(turns)} prior turns; no remote spend.")
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as f:
        f.write(f"DEMO_MARKER={marker}\n")


def verify(evidence: Path):
    state = json.loads(STATE_FILE.read_text())
    jar = http.cookiejar.MozillaCookieJar(str(COOKIE_FILE))
    jar.load(ignore_discard=True, ignore_expires=True)
    marker = state["marker"]
    deadline = time.monotonic() + 600
    found_request = False
    found_reply = ""
    reply_metadata = {}
    while time.monotonic() < deadline:
        now_model, _ = selected_model(ask("/api/bridge/models", jar=jar))
        if now_model != state["model"]:
            raise RuntimeError("Provider selection changed during the recorded turn.")
        turns = turns_from(ask("/api/bridge/conversation", jar=jar))
        # The marker is unique to the guest-initiated live turn and must occur
        # after the preflight baseline, not in an older conversation.
        prior = state["before_turns"]
        recent = turns[max(0, prior - 1):]
        for i, turn in enumerate(recent):
            if marker in text_of(turn) and role_of(turn) in ("user_turn", "user", ""):
                found_request = True
                for reply in recent[i+1:]:
                    if role_of(reply) in ("assistant_turn", "assistant"):
                        text = text_of(reply)
                        if text.strip():
                            found_reply = text
                            reply_metadata = {key: str(reply[key]) for key in ("model", "provider") if key in reply}
                        break
                break
        if found_reply:
            break
        time.sleep(12)
    evidence.mkdir(parents=True, exist_ok=True)
    receipt = {
        "guest_initiated_prompt_found": found_request,
        "verified_assistant_reply": bool(found_reply),
        "configured_model": state["model"],
        "provider_kind": state["kind"],
        "unique_demo_marker": marker,
        "reply_metadata": reply_metadata,
        "reply_model_metadata_matches_selected": bool(
            any(state["model"] == value for value in reply_metadata.values())
        ),
        "verification": "authenticated read of live durable conversation after guest submission; host-attested local selection is not cryptographic reply origin proof"
    }
    (evidence / "MODEL_REPLY_VERDICT.json").write_text(json.dumps(receipt, indent=2))
    if found_reply:
        (evidence / "MODEL_REPLY.txt").write_text(found_reply)
        print(f"VERIFIED: a new assistant reply followed a guest request under the verified local {state['model']} model selection.")
    else:
        raise RuntimeError("Live guest conversation did not produce a verified new assistant turn; never present video as a successful model conversation.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["preflight", "verify"])
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            preflight()
        else:
            verify(args.evidence)
    except (RuntimeError, error.URLError, ValueError, TimeoutError) as exc:
        print(f"DEMO INCOMPLETE: {exc}", file=sys.stderr)
        sys.exit(2)
