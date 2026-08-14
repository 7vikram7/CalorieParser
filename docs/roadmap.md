# CalorieParser — Future Roadmap

## Phase 0: Harden what exists (immediate)

Priority fixes from pressure test:

- [x] **Rate-limit `/v1/foods/estimate`** — add `slowapi` or similar. 5 req/min per IP for unauthenticated, 15/min for authenticated users. *(done 2026-08-09, live on Render)*
- [x] **Lock CORS** — set `ALLOWED_ORIGINS` to your Vercel domain + `http://localhost:3000` only. *(done 2026-08-09, live on Render)*
- [x] **Fix `responded_at`** — use a real UTC timestamp instead of the string `"now()"`. *(done 2026-08-09 — used `datetime.now(timezone.utc).isoformat()`, not `datetime.utcnow()` which is deprecated as of Python 3.12)*
- [x] **Cap input length** — reject `/estimate` descriptions > 500 characters. *(done 2026-08-09, live on Render)*
- [x] **Add pagination** — `limit` + `offset` params on all list endpoints (logs, workouts, foods). Default limit: 50. *(done 2026-08-09, live on Render)*
- [x] **Reuse Supabase base client** — create once, clone per-request with different auth header. *(done 2026-08-09, live on Render)*

Two more real bugs found by a follow-up stress test (2026-08-10), not on the
original list:

- [x] **`POST /v1/foods` 500 error** — `create_custom_food` used
  `model_dump()` instead of `model_dump(mode="json")`, so `Decimal` fields
  broke Supabase's internal `json.dumps()`. This was the actual cause of
  "Failed to fetch" when logging a meal in the UI. *(fixed and verified
  end-to-end against a real user, 2026-08-10)*
- [x] **Render free-tier cold start had no UX handling** — first request
  after 15 min idle could take 30-50s with no feedback. Added a pre-warm
  ping on app load (to `/v1/exercises`, not `/health` — see
  `docs/accounts.md` for why) and a "waking up the server" message if the
  estimate call is still pending after 4s. *(done 2026-08-10)*

---

## Phase 1: Polish the MVP (1-2 weeks)

### Backend
- [ ] Add `GET /v1/logs/summary?period=week|month` — aggregate calories/macros by day
- [ ] Add `DELETE /v1/foods/{food_id}` (cascades delete related logs — confirm with user first)
- [ ] Add `PATCH /v1/workouts/{workout_id}` — edit name/notes/date
- [x] Add `DELETE /v1/workouts/{workout_id}` — cascade deletes sets *(done 2026-08-13)*
- [x] Add `PATCH /v1/logs/{log_id}` — edit quantity/meal_type/date on a logged meal *(done 2026-08-13; not originally listed here but same category of gap. Found and fixed a pre-existing bug while adding it: `food_logs` had select/insert/delete RLS policies but no update policy, so every UPDATE silently affected 0 rows — added `backend/sql/004_food_logs_update_policy.sql`)*
- [ ] Error monitoring (Sentry free tier or structured logging to Render's log drain)
- [ ] Environment-aware config: dev vs. production settings (debug mode, CORS, etc.)

### Frontend
- [x] Protected routes (redirect to sign-in if not authenticated) *(verified 2026-08-13 — the app is a single page (`src/app/page.tsx`) that already gates everything behind `if (!user) return <AuthForm />`; no other route exists to leak into, and every API call is independently JWT-verified server-side regardless of frontend state. No code change needed, just confirmed rather than assumed.)*
- [x] Loading skeleton states instead of "Loading…" text *(done 2026-08-13 — shared `Skeleton.tsx`/`LoadingState` used across Diet, Workouts, Coach, Profile; still shows the cold-start "waking up" message once loading has clearly gone past normal latency)*
- [x] Date picker to view past days' logs (not just today) *(done 2026-08-11 — prev/next day buttons plus a date input on the Diet tab, `DailyLog.tsx`)*
- [ ] Weekly calorie summary chart (simple bar chart — recharts or similar)
- [x] Edit/delete logged meals *(delete already existed; edit added 2026-08-13 via `PATCH /v1/logs/{id}` — inline quantity/meal_type editor on the Diet tab)*
- [ ] Responsive mobile layout (already partly there with Tailwind, but test on real devices)
- [ ] PWA manifest + service worker (so it feels app-like on mobile without a native app)

### Workout logging redesign
Full plan: [`docs/workout-redesign-plan.md`](workout-redesign-plan.md) — the
original set-by-set model doesn't match how casual users actually log
workouts. Adds a quick-summary + highlights/PR path while keeping the
detailed set-by-set flow as the power-user option.
- [x] Schema migration — `workouts.source/intensity/calories_burned/avg_heart_rate`, `workout_sets.is_pr` *(done 2026-08-13, `backend/sql/003_workout_redesign.sql`)*
- [x] Backend — models + routes for the new fields, server-side PR auto-detection on set creation *(done 2026-08-13, verified: PR flagged correctly across weight increases/decreases and scoped per-exercise, not globally)*
- [x] Frontend — WorkoutsTab redesigned (intensity toggle, PR badges on highlights; existing set-by-set flow preserved as the same unified form, so it still serves power users) *(done 2026-08-13)*
- [ ] Tier 1 (Apple Health/Google Fit auto-import) explicitly deferred to Phase 4 (Mobile App)

---

## Phase 2: Coach Features (2-4 weeks)

### Backend
- [ ] Notification system (coach sends invite → athlete gets notified)
- [ ] `GET /v1/coaches/athletes/{id}/summary` — coach dashboard endpoint (this week's totals, compliance %)
- [ ] Coach can leave comments/notes on an athlete's day ("great protein intake today")

### Frontend
- [ ] Coach dashboard view (list athletes, click to see their logs/workouts)
- [ ] Invite flow (coach types athlete email → athlete sees pending invite → accept/decline)
- [ ] Role-based UI (show coach features only if `profiles.is_coach` is true)

---

## Phase 3: Smarter AI — Agentic Patterns (4-8 weeks)

This is where you learn agent orchestration by evolving the `/estimate` endpoint.
Full detailed plan (router design, cost model, Ollama's role, phase-by-phase
implementation notes): [`docs/agent-architecture-plan.md`](agent-architecture-plan.md).
**Design-only for now — no code changes until the workout redesign above ships.**

### 3a: Tool Use (function calling)
- [x] Give Gemini access to a nutrition DB tool (USDA FoodData Central API — free) *(done 2026-08-14, `backend/app/core/usda.py` + `backend/app/api/v1/foods.py`)*
- [x] Flow: user says "chicken tikka masala" → agent searches USDA → finds real data → augments estimate with verified numbers → higher confidence score *(verified live: a multi-item meal correctly triggered 4 parallel tool calls, USDA returned real per-100g data for 3/4 items and gracefully empty results for the one with no good match)*
- [x] Learn: function/tool definitions, structured tool responses, grounding AI in real data
- [x] **Unplanned but necessary: pulled a minimal piece of the Phase 3b router into 3a.** Discovered mid-build that Gemini's free tier is actually capped at **20 requests/day** per model (not "15 RPM, 1M tokens/day" as previously documented — that number was never verified and was wrong). The tool-calling flow costs 2 Gemini calls per estimate instead of 1; applying it to every request would have roughly halved the app's daily capacity for its whole core feature. Added `_needs_grounding()` in `foods.py` — a heuristic gate (multi-item or long descriptions get the grounded 2-call path, simple ones keep the original 1-call path) — matching the exact routing logic already sketched in `docs/agent-architecture-plan.md`'s Phase 3b pseudocode, just arriving a phase early because the quota math forced the issue. See `docs/agent-architecture-plan.md` for the full writeup.
- [x] **Also found and fixed:** Gemini's SDK default retry policy (5 attempts, exponential backoff up to 60s each) turned a single "high demand" 503 into multi-minute hangs during testing. Tightened to `attempts=2, max_delay=3s` per call.

### 3b: Routing + Caching + a Second Provider
*(Renamed from "Multi-step Chains" — the original per-item-parsing chain
below is now planned as a later 3d/3e refinement once multi-agent
orchestration exists; what actually got built here was forced by the
Gemini 20-req/day quota discovery and closely followed
`docs/agent-architecture-plan.md`'s original 3b routing/caching sketch,
plus adding Groq as a second, effectively-unlimited-quota provider.)*
- [x] Add Groq (`llama-3.3-70b-versatile`, JSON mode) as a second LLM
  provider, alongside Gemini *(done 2026-08-14)*
- [x] Provider abstraction — `backend/app/core/llm.py` now owns all
  provider-specific code (`google.genai` and `groq` SDKs); `foods.py` only
  calls `estimate_simple()`/`estimate_grounded()`/cache functions, no
  provider imports *(done 2026-08-14, `backend/app/core/gemini.py` deleted,
  logic absorbed into `llm.py`)*
- [x] Route simple descriptions to Groq instead of Gemini (`_needs_grounding()`
  in `foods.py`, unchanged from 3a) — this alone removes ~all everyday
  estimate traffic from Gemini's 20/day budget, since only multi-item/long
  descriptions still use it *(done 2026-08-14)*
- [x] Fallback: `estimate_grounded()` catches Gemini
  429/503/504 (quota exhausted / overloaded / timed out) and retries via
  Groq instead of failing the request *(done 2026-08-14 — verified against
  **real** exhausted-quota 429s and a real "high demand" 503 hit live
  during testing, not simulated; also found and fixed two gaps in the
  fallback's error allowlist, both live-caught rather than hypothesized:
  a 504 from a tightened client timeout, then — found via the user's own
  production test pass — a genuine client-side `httpx.TimeoutException`
  (request never got a response at all, vs. the API returning a 504
  payload), which isn't an `errors.APIError` subclass and was leaking
  through as a raw 502 requiring a manual retry until
  `_is_gemini_unavailable()` was widened to catch it directly)*
- [x] Cache: `estimate_cache` table (`backend/sql/005_estimate_cache.sql`),
  keyed by SHA256 hash of the lowercased/trimmed description, checked
  before calling any provider — a repeat description costs zero LLM calls
  *(done 2026-08-14, accessed via the service-role client since the table
  has no per-user owner and the endpoint itself is unauthenticated;
  verified locally — a repeat "a banana" request returned in ~0.24s vs.
  ~1.9s uncached, with byte-identical output confirming the cache path,
  not a re-generated match)*
- [ ] Step 1: Parse meal into individual food items ("2 eggs, toast, butter" → 3 items)
- [ ] Step 2: Estimate each item separately
- [ ] Step 3: Sum totals, cross-check plausibility
- [ ] Step 4: Return combined estimate with per-item breakdown
- [ ] Learn: LangChain/LangGraph sequential chains, intermediate state

### 3c: Memory / Personalization
- [ ] Store user's dietary preferences and past corrections
- [ ] "Last time you logged 'protein shake' you corrected it from 30g to 25g protein — using your corrected value"
- [ ] Learn: RAG (retrieval-augmented generation), vector embeddings, conversation memory

### 3d: Multi-Agent Orchestration
*(Built out of order, ahead of 3c — this phase didn't depend on memory/
personalization existing first, and was the natural next step after 3b's
routing/caching/Groq work.)*
- [x] Agent 1 (Parser): breaks description into food items *(done
  2026-08-14, Groq, JSON mode — `backend/app/core/agents.py:_parse_meal`)*
- [x] Agent 2 (Researcher): looks up each item in nutrition databases
  *(done 2026-08-14, USDA FoodData Central, no LLM — run concurrently via
  a thread pool since latency has mattered in every phase so far;
  `_research_items`)*
- [x] Agent 3 (Estimator): combines research + LLM reasoning for final
  numbers *(done 2026-08-14, Groq — `_estimate_nutrition`, receives prior
  validation failures as feedback text on a retry)*
- [x] Agent 4 (Validator): checks if totals make physical sense (e.g. 5000
  cal for "a salad" = reject) *(done 2026-08-14, rules-based, no LLM —
  `_validate_estimate`: rejects negative values, calories outside 0-5000,
  and calories that don't roughly match protein\*4 + carbs\*4 + fat\*9
  within 35%. Fails back to the estimator with the specific errors as
  feedback, up to 2 retries, then returns the last attempt regardless
  rather than blocking the user on a persistent validation failure)*
- [x] Learn: LangGraph multi-agent, delegation, agent communication
  *(LangGraph 1.2.11, not CrewAI — see `docs/agent-architecture-plan.md`
  and the new Level 10 in `docs/learning-log.md`)*
- [x] **Wired as the new primary path for complex/multi-item meals**,
  ahead of the older single-shot Gemini tool-calling flow from 3a, which
  now sits one layer down as a fallback: agent pipeline fails → Gemini
  grounded flow → plain Groq estimate, so this endpoint still effectively
  never 502s. All three layers verified end-to-end, including forcing a
  simulated pipeline bug to confirm the fallback actually fires.
- [x] **Also found and fixed:** the app had no `logging.basicConfig()`
  call anywhere, so every `logger.info()` call app-wide (not just the new
  agent pipeline's per-node logging) was being silently dropped — only
  `.warning()`/`.error()` calls were ever visible, by accident of Python's
  default root logger level. Fixed in `backend/app/main.py`; the agent
  pipeline's parse/research/estimate/validate steps (including per-node
  timing) are now genuinely visible in Render's log viewer, which was the
  whole point of adding them.

### 3e: Model Routing
- [ ] Simple/known foods → fast/cheap model (Gemini Flash)
- [ ] Complex/ambiguous meals → stronger model (Gemini Pro or Claude via API)
- [ ] Learn: routing logic, cost optimization, model selection strategies

---

## Phase 4: Mobile App (8-12 weeks)

### Option A: React Native (Expo)
- Shares TypeScript/API client code with the web frontend
- Same Supabase auth SDK works on mobile
- Fastest path given your existing frontend code

### Option B: Native iOS (Swift)
- Leverages your iOS/Swift background
- Better performance, native feel
- Supabase has a Swift SDK
- More work (separate codebase) but better learning for your career

### Shared mobile features (either option):
- [ ] Camera → photo of food → describe via vision model (Gemini supports image input)
- [ ] Barcode scanner → look up packaged foods (Open Food Facts API — free)
- [ ] Push notifications (coach comments, daily reminders)
- [ ] Offline mode (queue logs locally, sync when online)
- [ ] Apple Health / Google Fit integration (sync weight, workouts)

---

## Phase 5: Scale & Production Hardening (ongoing)

- [ ] Move to Render paid tier (no sleep) or migrate to Railway/Fly.io
- [ ] Add CI/CD (GitHub Actions: lint, test, deploy on merge to main)
- [ ] Add tests (pytest for backend, Playwright for frontend E2E)
- [ ] Custom domain (`app.calorieparser.com`)
- [ ] HTTPS everywhere (Render and Vercel handle this by default)
- [ ] Database backups (Supabase Pro or pg_dump cron)
- [ ] Analytics (PostHog free tier — understand what features get used)
- [ ] GDPR compliance (data export, account deletion)

---

## Tech learning path (maps to your goals)

| Phase | What you learn |
|-------|---------------|
| 0-1 | Backend fundamentals, REST API design, auth flows |
| 2 | Multi-user data access patterns, RLS in practice |
| 3a | LLM tool use / function calling |
| 3b | Chain-of-thought, multi-step reasoning |
| 3c | RAG, embeddings, vector search |
| 3d | Multi-agent systems, orchestration frameworks |
| 3e | Production AI patterns (cost, latency, routing) |
| 4 | Mobile development (cross-platform or native) |
| 5 | DevOps, CI/CD, monitoring, production operations |
