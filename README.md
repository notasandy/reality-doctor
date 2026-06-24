# 🩺 Reality Doctor

> An AI assistant that diagnoses censorship-circumvention setups — VLESS + Reality, MTProxy, zapret — and tells you the **minimal fix**, grounded in real, vetted guides instead of hallucinated from memory.

![Status](https://img.shields.io/badge/status-WIP%20(M1)-yellow)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

You paste your error, your `journalctl -u xray` log, or `blockcheck` output — Reality Doctor
retrieves the relevant section of the [Anti-Censorship Handbook](https://github.com/notasandy/anti-censorship-handbook)
and answers with a concrete fix and a citation, **never inventing config you'd paste into a
broken server.**

## 📖 What this is

A Retrieval-Augmented Generation (RAG) service specialised for one painful task: debugging
self-hosted anti-censorship setups. It reuses a production-style RAG engine and swaps the
knowledge base to the handbook, then adds the safety layers that matter for this domain.

Built as a real product (it funnels people who give up to a ready-made service) **and** as a
portfolio piece: RAG, vector search, LLM orchestration, secret-scrubbing, deterministic
routing, and grounded-output validation.

## 🏗️ How it works (target architecture)

```
Telegram message
  └─> scrub:      strip vless:// / vmess:// secrets BEFORE logging → "I removed your key"
  └─> rate-limit: per chat_id (protect the budget)
  └─> router:     known error (i/o timeout, clock skew, busy port)? → canned answer, STOP (0 tokens)
                  otherwise ↓
  └─> RAG:        embed → Qdrant top-k over the handbook → LLM with a strict "doctor" prompt
  └─> validate:   answer contains a config block? → JSON-schema check; invalid → ask to rephrase
  └─> reply + 👍/👎 + footer "don't want to tinker? @ExtenVPNBot"
```

The retrieval core (`src/ingestion`, `src/retrieval`, `src/generation`) is a reused, working
RAG pipeline: header-aware markdown chunking → `all-MiniLM-L6-v2` embeddings → Qdrant search →
grounded LLM answer with source citations.

## 🗺️ Roadmap

- [x] **M1** — Knowledge base = the Anti-Censorship Handbook (re-indexed), `/ask` answers
      circumvention questions.
- [x] **M2** — Safety layer: auto-scrub of secrets + deterministic FAQ router (before the LLM),
      with tests.
- [x] **M3** — Doctor prompt ("minimal fix, only from context") + JSON output validation
      (broken config blocks are never shown), with tests.
- [x] **M4** — Telegram front-end (`python -m src.bot.telegram_bot`): auto-scrub →
      FAQ router → rate-limited RAG, 👍/👎 feedback log, `@ExtenVPNBot` footer.
      LLM provider is swappable (`LLM_PROVIDER=groq` free by default, `claude` optional).
- [ ] **M5** — Eval set (real log → correct fix pairs) + launch (Habr, net4people, r/selfhosted).

## 🚀 Quick start (M1 — ask the handbook over HTTP)

```bash
# 1. Install deps
uv sync

# 2. Configure
cp .env.example .env   # put your GROQ_API_KEY

# 3. Start Qdrant
docker compose up -d qdrant

# 4. Load the handbook as the knowledge base
#    (clone it, then point the ingester at its markdown)
git clone --depth=1 https://github.com/notasandy/anti-censorship-handbook /tmp/handbook
mkdir -p data/raw
cp /tmp/handbook/README*.md data/raw/
cp -r /tmp/handbook/docs data/raw/docs
find data/raw -type f ! -name '*.md' -delete
uv run python -m scripts.ingest

# 5. Run the API
uv run uvicorn src.api.main:app --reload
```

```bash
curl -N -X POST http://localhost:8000/ask/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "My Xray client connects but there is no internet. What do I check?"}'
```

## 🤖 Run the Telegram bot (free)

Everything runs at **zero cost** by default: local embeddings, self-hosted Qdrant,
and Groq's free LLM tier. Claude Haiku is an optional quality upgrade, off by default.

```bash
# In .env: TELEGRAM_BOT_TOKEN=<from @BotFather>, GROQ_API_KEY=<from console.groq.com>
# (LLM_PROVIDER defaults to groq — free)
uv run python -m src.bot.telegram_bot
```

The bot scrubs secrets from every message, answers common errors from the FAQ router
(zero tokens), falls back to RAG for the hard ones (rate-limited per chat/day), and
logs 👍/👎 to `data/feedback.jsonl` to build an eval set.

## ⚠️ Privacy

Every incoming message is run through `src/safety/scrub.py` **before it is logged or sent to a
model**: share links (`vless://`, `vmess://`, `ss://`, `trojan://`, `tuic://`, `hysteria2://`)
have their credentials, server address and remark stripped; standalone UUIDs and
`privateKey`/`password`/`shortId` values are redacted. The bot keeps only the diagnostic
structure (protocol, transport, `sni`, `flow`, port) and tells you what it removed.

It's conservative, not a guarantee — still prefer placeholders over real secrets.

## 📄 License

MIT — see [LICENSE](LICENSE). Guide content is sourced from the
[Anti-Censorship Handbook](https://github.com/notasandy/anti-censorship-handbook) (CC-BY-4.0).
