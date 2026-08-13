# Agent Architecture & Cost Optimization — Plan

> Status: **Design-only, no code changes yet** (per explicit instruction
> 2026-08-13 — this ships after the workout redesign, not alongside it).
> This is the detailed elaboration of `docs/roadmap.md` Phase 3.

## The vision

```
USER REQUEST: "I had butter chicken with 2 naan and a lassi"
        │
        ▼
ROUTER (lightweight, fast) — decides simple vs. complex/ambiguous
  Runs on: Ollama local (Llama 3.1 8B) or rules-based. Cost: $0
        │
        ├─ simple ──────────────► FAST PATH: single Gemini Flash call
        │                          "banana" → instant, ~0.001¢
        │
        └─ complex/ambiguous ──► AGENT PATH: Orchestrator (LangGraph)
                                    1. Parser Agent — split into items
                                    2. Researcher Agent — USDA FoodData
                                       Central lookup per item
                                    3. Estimator Agent — combine research
                                       + LLM reasoning for portions
                                    4. Validator Agent — sanity-check
                                       totals, reject+retry if implausible
                                    Cost: ~0.01¢ (4 calls)
```

## Where each piece fits

| Component | Tech | Why | Cost |
|---|---|---|---|
| Router | Ollama (Llama 3.1 8B) locally, or simple heuristics | <100ms decision, zero API cost | $0 |
| Fast path | Gemini Flash (current) | Simple foods, high confidence | Free tier |
| Agent orchestrator | LangGraph (Python) | Multi-step flow, retries, state | $0 (library) |
| Parser agent | Gemini Flash | Break meal into items | Free tier |
| Researcher agent | USDA FoodData Central API (tool call) | Ground-truth nutrition data | Free (gov API) |
| Estimator agent | Gemini Flash or Pro | Reason about portions + research | Free/cheap |
| Validator agent | Rules-based + lightweight LLM | Sanity checks (cal/macro ratios) | $0 |

## Routing logic (pseudocode)

```python
def route(description: str) -> str:
    word_count = len(description.split())
    if word_count <= 3:
        return "fast"  # "a banana", "2 eggs"

    if matches_previous_log(description):
        return "cache"  # same description → same response, zero API calls

    if word_count > 8 or "and" in description or "," in description:
        return "agent"  # multi-item meal needs parsing

    return "fast"
```

## Ollama's role — complement to Gemini, not a replacement

| Use case | Why local | Model |
|---|---|---|
| Router decisions | Latency-critical, no data leaves device | Llama 3.1 8B (~5GB RAM) |
| Food item parsing | Simple structured extraction | Llama 3.1 8B |
| Validator | "Does 5000 kcal for a salad make sense?" | Llama 3.1 8B |
| Meal history matching | Embedding similarity search | nomic-embed-text |
| Cache lookup | "They logged this exact phrase before" | Embeddings only |

Still needs Gemini (cloud): the actual nutritional estimation (needs world
knowledge about food), complex multi-cuisine parsing, anything that
benefits from a larger model.

## Cost model at scale

| Users/day | Requests | Without optimization | With routing + cache |
|---|---|---|---|
| 10 | 30 | 30 Gemini calls | 30 Gemini (all free tier) |
| 100 | 300 | 300 Gemini calls | ~100 Gemini + 200 cache/local |
| 1000 | 3000 | Exceeds free tier | ~500 Gemini + 2500 cache/local |

At 1000 users/day you'd need Gemini's paid tier (~$0.15/1M tokens ≈
$2/month). Routing + caching pushes that threshold much higher.

## Implementation phases (maps to `docs/roadmap.md` Phase 3a-3e)

- **3a — Tool use:** give Gemini a USDA FoodData Central tool; on uncertain
  items it searches the DB first. Learn: function calling, tool defs.
- **3b — Routing:** simple heuristic router (no ML needed) + cache recent
  estimates. Learn: caching strategies, when to use AI vs. rules.
- **3c — Local model for routing (Ollama):** install on Render or dev-only;
  8B model for router decisions + validation. Learn: local LLM serving,
  latency tradeoffs.
- **3d — Full multi-agent (LangGraph):** Parser → Researcher → Estimator →
  Validator as a state graph, with retry-on-reject looping back to the
  Estimator with feedback. Learn: LangGraph state machines, agent comms.
- **3e — Embeddings for meal memory:** embed past meal descriptions
  (nomic-embed-text via Ollama, free); >0.95 similarity match returns the
  cached result with zero API calls. Learn: vector embeddings, similarity
  search, RAG basics.

## Architecture principle

**The route handler signature never changes.** The frontend always calls:

```
POST /v1/foods/estimate { "description": "..." }
```

What happens behind that endpoint evolves — today a single Gemini call,
later a router choosing fast/agent path, later still full cache/local/cloud
orchestration — but the contract the frontend depends on never does. The
complexity is invisible to the frontend.
