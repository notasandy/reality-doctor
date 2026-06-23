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
- [ ] **M2** — Safety layer: auto-scrub of secrets + deterministic FAQ router (before the LLM).
- [ ] **M3** — Doctor prompt ("minimal fix, only from context") + JSON-schema output validation.
- [ ] **M4** — Telegram front-end, rate-limiting, 👍/👎 feedback; swap LLM to Claude Haiku.
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

## ⚠️ Privacy

Reality Doctor is being built to **strip secrets from your input before anything is logged or
sent to a model** (M2). Until that lands, **do not paste real `vless://` links, private keys,
UUIDs or IPs.** Use placeholders.

## 📄 License

MIT — see [LICENSE](LICENSE). Guide content is sourced from the
[Anti-Censorship Handbook](https://github.com/notasandy/anti-censorship-handbook) (CC-BY-4.0).
