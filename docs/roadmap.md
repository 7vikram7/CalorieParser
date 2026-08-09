# CalorieParser — Future Roadmap

## Phase 0: Harden what exists (immediate)

Priority fixes from pressure test:

- [ ] **Rate-limit `/v1/foods/estimate`** — add `slowapi` or similar. 5 req/min per IP for unauthenticated, 15/min for authenticated users.
- [ ] **Lock CORS** — set `ALLOWED_ORIGINS` to your Vercel domain + `http://localhost:3000` only.
- [ ] **Fix `responded_at`** — use `datetime.utcnow().isoformat()` instead of the string `"now()"`.
- [ ] **Cap input length** — reject `/estimate` descriptions > 500 characters.
- [ ] **Add pagination** — `limit` + `offset` params on all list endpoints (logs, workouts, foods). Default limit: 50.
- [ ] **Reuse Supabase base client** — create once, clone per-request with different auth header.

---

## Phase 1: Polish the MVP (1-2 weeks)

### Backend
- [ ] Add `GET /v1/logs/summary?period=week|month` — aggregate calories/macros by day
- [ ] Add `DELETE /v1/foods/{food_id}` (cascades delete related logs — confirm with user first)
- [ ] Add `PATCH /v1/workouts/{workout_id}` — edit name/notes/date
- [ ] Add `DELETE /v1/workouts/{workout_id}` — cascade deletes sets
- [ ] Error monitoring (Sentry free tier or structured logging to Render's log drain)
- [ ] Environment-aware config: dev vs. production settings (debug mode, CORS, etc.)

### Frontend
- [ ] Protected routes (redirect to sign-in if not authenticated)
- [ ] Loading skeleton states instead of "Loading…" text
- [ ] Date picker to view past days' logs (not just today)
- [ ] Weekly calorie summary chart (simple bar chart — recharts or similar)
- [ ] Edit/delete logged meals
- [ ] Responsive mobile layout (already partly there with Tailwind, but test on real devices)
- [ ] PWA manifest + service worker (so it feels app-like on mobile without a native app)

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

This is where you learn agent orchestration by evolving the `/estimate` endpoint:

### 3a: Tool Use (function calling)
- [ ] Give Gemini access to a nutrition DB tool (USDA FoodData Central API — free)
- [ ] Flow: user says "chicken tikka masala" → agent searches USDA → finds real data → augments estimate with verified numbers → higher confidence score
- [ ] Learn: function/tool definitions, structured tool responses, grounding AI in real data

### 3b: Multi-step Chains
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
- [ ] Agent 1 (Parser): breaks description into food items
- [ ] Agent 2 (Researcher): looks up each item in nutrition databases
- [ ] Agent 3 (Estimator): combines research + LLM reasoning for final numbers
- [ ] Agent 4 (Validator): checks if totals make physical sense (e.g. 5000 cal for "a salad" = reject)
- [ ] Learn: CrewAI or LangGraph multi-agent, delegation, agent communication

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
