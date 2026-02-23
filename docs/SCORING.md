# Scoring Model

How opportunities are scored 0–100 for relevance. Two modes: **heuristic stub** (default) or **LLM** (OpenAI/Ollama).

---

## Heuristic Stub (Default)

When no LLM is configured, a rule-based stub produces scores with small cumulative boosts and penalties.

### Boosts

| Signal | Points | Condition |
|--------|--------|-----------|
| Similarity to examples | -15 to +15 | Overlap with good/bad fit examples |
| PDF present | +3 | Attachment text successfully extracted |
| Category SRV | +4 | Services (excludes non-tech: furniture, transportation, etc.) |
| Keyword in scope | +5 each | Keyword in title or first 300 chars (max 3) |

### Penalties

| Signal | Points | Condition |
|--------|--------|-----------|
| Category CNST | -8 | Construction |
| Non-tech commodity | -10 | Commodity codes 56xxxx (furniture), 90xxxx (cleaning) |
| Non-tech title/lead | -10 | Phrases: office furniture, GPU hardware, transportation, etc. |

### Confidence Dampening

Lower confidence reduces the final score:

| Confidence | Penalty |
|------------|---------|
| high | 0 |
| medium | -3 |
| low | -8 |
| insufficient_text | -15 |

---

## LLM Scoring (Optional)

Set `RFP_FINDER_LLM_PROVIDER=openai` (or `ollama`) and provide credentials. The LLM receives the opportunity text and profile, and returns score, reasons, risks, and evidence.

```bash
poetry install -E llm
# .env: OPENAI_API_KEY=sk-... and RFP_FINDER_LLM_PROVIDER=openai
```

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required for `RFP_FINDER_LLM_PROVIDER=openai` |
| `RFP_FINDER_LLM_PROVIDER` | `ollama` \| `openai` \| unset (stub) |
| `RFP_FINDER_LLM_MODEL` | Model name (default: `gpt-4o-mini` for OpenAI, `llama3.2` for Ollama) |

Load from `.env` (copy `.env.example`). Never commit `.env`.
