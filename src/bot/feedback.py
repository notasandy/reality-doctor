"""Append-only 👍/👎 feedback log.

Builds the eval dataset over time: which question got which answer, and whether
it helped. The question is already scrubbed of secrets before it reaches here.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class FeedbackStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, chat_id: int, question: str, answer: str, route: str | None, vote: str) -> None:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "chat_id": chat_id,
            "route": route,            # FAQ rule, or null for RAG answers
            "vote": vote,              # "up" | "down"
            "question": question,      # already scrubbed
            "answer": answer,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
