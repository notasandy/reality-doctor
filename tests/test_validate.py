"""Tests for M3 JSON output validation.

    uv run pytest
    python -m tests.test_validate
"""
from __future__ import annotations

from src.safety.validate import validate_answer


def test_valid_json_block_passes():
    ans = 'Set the port:\n```json\n{"port": 443, "protocol": "vless"}\n```\nSource: guide.'
    assert validate_answer(ans).ok


def test_jsonc_with_comments_and_trailing_comma_passes():
    ans = (
        "```json\n"
        "{\n"
        '  "port": 443, // standard HTTPS\n'
        '  "serverNames": ["www.microsoft.com"],\n'  # trailing comma below
        "}\n"
        "```"
    )
    assert validate_answer(ans).ok


def test_url_with_double_slash_not_treated_as_comment():
    ans = '```json\n{"dest": "https://example.com", "port": 443}\n```'
    assert validate_answer(ans).ok


def test_broken_json_block_fails():
    ans = '```json\n{"port": 443 "protocol": "vless"}\n```'  # missing comma
    res = validate_answer(ans)
    assert not res.ok and res.issues


def test_non_json_fence_ignored():
    ans = "Run this:\n```bash\nsystemctl restart xray\n```\nDone."
    assert validate_answer(ans).ok


def test_no_block_is_ok():
    assert validate_answer("Just set flow to xtls-rprx-vision on both sides.").ok


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ✓ {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} tests passed")
