"""Validate config blocks in an LLM answer before we show them to the user.

A syntactically broken config is worse than a plain error: the user pastes it,
Xray won't start, and they blame the bot. So we extract every fenced ```json
block from the answer and make sure it actually parses. Comments and trailing
commas are tolerated (Xray accepts them), but genuine syntax errors are caught.

If validation fails the caller should NOT show the block — better to ask the
user to rephrase than to hand them config that breaks their server.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

_FENCE_RE = re.compile(r"```(?:json|jsonc)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass
class ValidationResult:
    ok: bool
    issues: list[str] = field(default_factory=list)


def _strip_jsonc(s: str) -> str:
    """Remove // and /* */ comments and trailing commas, respecting strings."""
    out: list[str] = []
    i, n = 0, len(s)
    in_str = False
    escaped = False
    while i < n:
        c = s[i]
        if in_str:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            while i < n and s[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i + 1 < n and not (s[i] == "*" and s[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    result = "".join(out)
    result = re.sub(r",(\s*[}\]])", r"\1", result)  # trailing commas
    return result


def validate_answer(answer: str) -> ValidationResult:
    """Check every JSON-looking fenced block in the answer parses."""
    issues: list[str] = []
    for idx, block in enumerate(_FENCE_RE.findall(answer), start=1):
        text = block.strip()
        if not text or text[0] not in "{[":
            continue  # not a JSON object/array — skip (e.g. a shell snippet)
        try:
            json.loads(_strip_jsonc(text))
        except json.JSONDecodeError as e:
            issues.append(f"config block {idx}: {e.msg} (line {e.lineno}, col {e.colno})")
    return ValidationResult(ok=not issues, issues=issues)
