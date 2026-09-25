#!/usr/bin/env python3
"""One-turn, credential-safe verification of the owner's live GPT-120B conversation.

Never sends a model turn itself. The one visible turn must be initiated in the
Synapse guest browser; this host-side tool only checks provider and continuity.
"""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import re
import ssl
import sys
import time
from urllib import request, error

SITE = "https://www.beastboxcosmos.xyz"
COOKIE_FILE = Path("/tmp/synapse-gpt120b-demo-session.cookies")
STATE_FILE = Path("/tmp/synapse-gpt120b-demo-status.json")
TIMEOUT = 25


def ask(path, payload=None, jar=None):
    opener = request.build_opener(request.HTTPCookieProcessor(jar))
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    req = request.Request(SITE + path, data=data, headers=headers, method="POST" if data else "GET")
    with opener.open(req, timeout=TIMEOUT) as res:
        return json.load(res)


def selected_model(response):
    profile = response.get("profile") if isinstance(response, dict) else None
    if not isinstance(profile, dict):
        raise RuntimeError("The authenticated provider endpoint returned no selected profile.")
    model = str(profile.get("model") or profile.get("model_id") or "")
    if not re.search(r"gpt[-_ ]?oss.{0,20}120b", model, re.IGNORECASE):
        raise RuntimeError(f"Selected model does not attest gpt-oss 120b (reported: {model[:70]!r}).")
    kind = str(profile.get("kind") or "")
    if kind.lower() in {"reference", "fixture", "mock"}:
        raise RuntimeError("The selected GPT-120B label points to a reference fixture, not verified inference.")
    return model, kind


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
    if os.environ.get("BEASTBOX_ALLOW_GPT120B_DEMO") != "YES_ONE_TURN":
        raise RuntimeError("Remote inference not approved: set repository Actions variable BEASTBOX_ALLOW_GPT120B_DEMO to YES_ONE_TURN.")
    jar = http.cookiejar.MozillaCookieJar(str(COOKIE_FILE))
    # Do not persist the entered password, a token, session response or private turns.
    ask("/api/session", {"password": password}, jar)
    status = ask("/api/status", jar=jar)
    if status.get("backendReachable") is not True:
        raise RuntimeError("Website is logged in, but its backend is not confirmed reachable.")
    model, kind = selected_model(ask("/api/bridge/provider", jar=jar))
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
    print(f"READY: owner session, reachable backend, selected {model}, {len(turns)} prior turns.")
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
        now_model, _ = selected_model(ask("/api/bridge/provider", jar=jar))
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
        "provider_origin_attested": bool(
            any(re.search(r"gpt[-_ ]?oss.{0,20}120b", value, re.IGNORECASE)
                for value in reply_metadata.values())
        ),
        "verification": "authenticated read of live durable conversation after guest submission; a configured label is not a model-origin attestation"
    }
    (evidence / "MODEL_REPLY_VERDICT.json").write_text(json.dumps(receipt, indent=2))
    if found_reply:
        (evidence / "MODEL_REPLY.txt").write_text(found_reply)
        print(f"VERIFIED: a new assistant reply followed guest request under configured {state['model']} profile. Inspect receipt for independent model-origin attestation.")
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
