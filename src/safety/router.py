"""Deterministic fast-path for the most common problems.

Before we spend a single LLM token, we try to match the user's message against
a small set of well-understood failure modes. A hit returns a canned, correct
answer (zero tokens, zero hallucination). A miss falls through to RAG.

Answers are short and point at the handbook. Localization (RU/FA) comes later;
for now everything is in English, matching the EN handbook mirror.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Rule:
    name: str
    pattern: re.Pattern
    answer: str


@dataclass
class RouteHit:
    rule: str
    answer: str


def _p(*alts: str) -> re.Pattern:
    return re.compile("|".join(alts), re.IGNORECASE)


RULES: list[Rule] = [
    Rule(
        "connection_timeout",
        _p(r"i/?o timeout", r"connection timed? ?out", r"dial tcp .*timeout", r"can'?t connect", r"connection refused"),
        "**Looks like the port is unreachable.**\n"
        "1. On the server: `ufw status` — port `443/tcp` must be open.\n"
        "2. Check your VPS provider's panel — there's often a *separate* security group/firewall.\n"
        "3. Confirm Xray is listening: `ss -tlnp | grep 443`.\n"
        "See: VLESS+Reality guide → Step 1 & Troubleshooting.",
    ),
    Rule(
        "clock_skew",
        _p(r"clock", r"time .*(skew|sync|wrong)", r"rejected.*time", r"certificate.*not yet valid", r"system time"),
        "**Reality is time-sensitive — your clock is likely off.**\n"
        "Sync it: `timedatectl set-ntp true` (or `apt install -y ntp`).\n"
        "A clock that's off by more than ~a minute breaks the handshake on either side.",
    ),
    Rule(
        "port_in_use",
        _p(r"address already in use", r"port .*in use", r"bind:.*in use", r"listen tcp.*in use"),
        "**Port 443 is already taken by another service.**\n"
        "Find it: `ss -tlnp | grep ':443 '`. Either stop that service, or run Reality on a\n"
        "different port (e.g. 8443) and update the client. See: MTProxy guide → Step 0 for the same check.",
    ),
    Rule(
        "json_syntax",
        _p(r"invalid character", r"failed to parse", r"json.*(error|invalid)", r"unexpected end of json", r"trailing comma"),
        "**Your `config.json` has a syntax error.**\n"
        "Validate before restarting: `xray run -test -config /usr/local/etc/xray/config.json`.\n"
        "Most common cause: a trailing comma after the last item in a list/object.\n"
        "See: Troubleshooting → 'service won't start'.",
    ),
    Rule(
        "flow_mismatch",
        _p(r"flow", r"xtls-?rprx-?vision"),
        "**`flow` must be identical on server and client.**\n"
        "Both sides need `xtls-rprx-vision`. If one has it and the other doesn't, the\n"
        "connection fails or has no traffic. See: VLESS+Reality guide → Step 5/6.",
    ),
    Rule(
        "sni_mismatch",
        _p(r"\bsni\b", r"server ?name", r"servernames?"),
        "**SNI mismatch.** The client's `serverName`/`sni` must equal the server's\n"
        "`serverNames` (which equals your `dest` domain). A typo here looks like a silent\n"
        "failure. See: VLESS+Reality guide → Step 4 & Troubleshooting.",
    ),
    Rule(
        "no_traffic",
        _p(r"no internet", r"connects? but.*(no|nothing)", r"ip (didn'?t|not) chang", r"traffic .*bypass"),
        "**Connected but no traffic / IP unchanged.**\n"
        "1. Make sure the client is in proxy/global mode, not 'direct/bypass for all'.\n"
        "2. Check the system proxy or TUN is actually active.\n"
        "3. Verify at `https://whatismyipaddress.com`. See: VLESS+Reality guide → Step 7.",
    ),
    Rule(
        "dns_leak",
        _p(r"dns leak", r"dnsleak", r"dns .*(leak|provider)"),
        "**DNS leak.** Enable DNS proxying in the client, or use a TUN mode that intercepts\n"
        "DNS. Re-test at `https://dnsleaktest.com`. See: Troubleshooting → 'DNS leaks'.",
    ),
    Rule(
        "worked_then_stopped",
        _p(r"worked.*(stopped|no longer)", r"was working.*(stopped|now)", r"stopped working", r"suddenly (stopped|blocked)"),
        "**Worked, then stopped — likely your IP got probed/blocked.**\n"
        "Try a different `dest` (another popular domain with TLS 1.3 + h2) and restart Xray.\n"
        "If that doesn't help, it's probably IP-level blocking — consider a new IP/location.\n"
        "See: Troubleshooting → 'worked, then stopped'.",
    ),
]


def route(text: str) -> RouteHit | None:
    """Return a canned answer for a known problem, or None to fall through to RAG."""
    for rule in RULES:
        if rule.pattern.search(text):
            return RouteHit(rule=rule.name, answer=rule.answer)
    return None
