"""Tests for the M2 safety layer (scrub + router).

Runnable two ways:
    uv run pytest                 # if pytest is installed
    python -m tests.test_safety   # standalone, no deps
"""
from __future__ import annotations

from src.safety.router import route
from src.safety.scrub import scrub


# --- scrubbing ------------------------------------------------------------

def test_vless_link_credentials_removed():
    link = (
        "vless://2b7e1516-28ae-4d2a-a09c-1f2b3c4d5e6f@203.0.113.7:443"
        "?security=reality&encryption=none&pbk=AbC123pubKey_value&fp=chrome"
        "&type=tcp&flow=xtls-rprx-vision&sni=www.microsoft.com&sid=0123456789abcdef#MyServer"
    )
    out = scrub(link)
    t = out.text
    # secrets gone
    assert "2b7e1516-28ae-4d2a-a09c-1f2b3c4d5e6f" not in t
    assert "AbC123pubKey_value" not in t
    assert "0123456789abcdef" not in t
    assert "203.0.113.7" not in t
    assert "MyServer" not in t          # remark dropped
    # diagnostic structure kept
    assert "flow=xtls-rprx-vision" in t
    assert "sni=www.microsoft.com" in t
    assert "security=reality" in t
    assert out.changed and "a VLESS link" in out.redacted


def test_vmess_blob_fully_redacted():
    out = scrub("here is mine vmess://eyJ2IjoiMiIsInBzIjoidGVzdCJ9 thanks")
    assert "eyJ2" not in out.text
    assert "REDACTED_VMESS_CONFIG" in out.text


def test_standalone_uuid_and_kv():
    out = scrub('my id is 2b7e1516-28ae-4d2a-a09c-1f2b3c4d5e6f and "privateKey": "sEcReTpriv12345"')
    assert "2b7e1516-28ae-4d2a-a09c-1f2b3c4d5e6f" not in out.text
    assert "<UUID>" in out.text
    assert "sEcReTpriv12345" not in out.text
    assert "<redacted>" in out.text


def test_clean_text_untouched():
    msg = "My Xray client connects but there is no internet, what do I check?"
    out = scrub(msg)
    assert out.text == msg
    assert not out.changed
    assert out.notice() is None


# --- routing --------------------------------------------------------------

def test_router_matches_timeout():
    hit = route("xray log says dial tcp 1.2.3.4:443: i/o timeout")
    assert hit is not None and hit.rule == "connection_timeout"


def test_router_matches_port_in_use():
    hit = route("systemctl shows: listen tcp 0.0.0.0:443: bind: address already in use")
    assert hit is not None and hit.rule == "port_in_use"


def test_router_matches_clock():
    hit = route("certificate is not yet valid, maybe system time?")
    assert hit is not None and hit.rule == "clock_skew"


def test_router_miss_falls_through():
    assert route("how do I choose a good dest domain for my region?") is None


# --- standalone runner ----------------------------------------------------

if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ✓ {fn.__name__}")
    print(f"\n{passed}/{len(fns)} tests passed")
