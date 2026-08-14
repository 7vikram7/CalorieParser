# CalorieParser — Project Context

This file is read automatically by Claude Code at the start of any session in
this repo, on any machine. It exists so work can continue seamlessly without
relying on any one machine's local memory.

## What this project is

A calorie/food tracking app where both end users **and their coaches** can
track calorie/food logs and workout progress. Explicitly a learning project:
the user has a strong iOS/Swift background and is learning backend, database,
and web dev concepts by building this. See `docs/learning-log.md` for a
level-by-level log of concepts learned so far (architecture → hosting → DB/
security → backend → folder structure), written with iOS/Swift analogies.

Product scope: calorie/food tracking + workout tracking + coach access to
athlete data (all three in the current schema) + a mobile app (planned,
not started).

## Stack and why

| Layer | Tech | Hosted on | Why |
|---|---|---|---|
| Frontend | Next.js (App Router, TypeScript, Tailwind) | Vercel | Live at `https://frontend-six-khaki-k808d8a0hz.vercel.app` — see `docs/accounts.md`. Talks to Supabase directly for auth, and to the FastAPI backend for AI estimation + anything needing the service-role/Gemini key. |
| Backend | FastAPI (Python) | Render | Railway's free tier is gone (removed 2023); Render still has one. FastAPI kept as a separate service (not Next.js API routes) specifically so a future mobile app can call the same API. |
| DB + Auth | Supabase (Postgres) | Supabase | BaaS pattern: frontend reads directly from Supabase where possible; FastAPI only handles secrets/AI/complex logic. Auth is 100% Supabase's — FastAPI never issues tokens, only verifies them. |
| AI | Google Gemini (`gemini-flash-latest`) | called from FastAPI | Server-side only — key must never reach the browser. Switched from the original OpenAI plan specifically for the free tier, no billing required. Uses the `-latest` alias, not a pinned version — `gemini-2.0-flash` lost free-tier quota by 2026-08, so pinning is riskier than tracking Google's current recommended flash model. **Free tier limit corrected 2026-08-14** — the originally documented "15 RPM, 1M tokens/day" was wrong (never actually verified against a real quota error). The real, binding constraint, seen directly in a 429 response: `GenerateRequestsPerDayPerProjectPerModel-FreeTier` = **20 requests/day** for `gemini-3.7-flash` (what `-latest` currently resolves to) — not per-minute, per-day, and shared across local dev and production since they use the same API key. Design around this as a hard daily budget, not a throughput limit. |

## Current status (as of 2026-08-11)

- Backend is scaffolded at `backend/` — SQL schema, Pydantic models, and
  FastAPI routes all exist. Verified for real this time: installed Python
  3.12 + actual dependencies (not stubs) into `backend/.venv`, booted
  `uvicorn`, and hit `/health` and `/docs` over real HTTP — both worked, and
  an unauthenticated request to a protected route correctly returned 401.
- A Supabase project now exists (project ref `wniqdkbfmqqiqzxeqqis` — see
  `docs/accounts.md` for URL/keys, `docs/accounts.secrets.md` for the service
  role key, gitignored). **Schema is pushed** — `backend/sql/001_initial_schema.sql`
  and `002_seed_exercises.sql` have been applied directly via `psql` against
  the Supavisor session pooler (region `ap-northeast-1` — see
  `docs/accounts.md`; the direct `db.<ref>.supabase.co` host is IPv6-only and
  unreachable from networks without IPv6, so the pooler host is required).
  8 tables exist, RLS is enabled on all of them, and the 12-row exercise
  catalog is seeded.
- `POST /v1/foods/estimate` now calls Gemini instead of the originally
  planned OpenAI (no free tier fit the "test thoroughly on free tiers" goal —
  see `docs/accounts.md`). Real `GEMINI_API_KEY` is configured and the
  endpoint is verified working end-to-end via `gemini-flash-latest`
  (`gemini-2.0-flash`, the originally planned pinned version, turned out to
  have zero free-tier quota by this point — see `docs/accounts.md`).
- Backend is deployed to Render at `https://calorieparser-backend.onrender.com`
  — see `docs/accounts.md` for details.
- Frontend at `frontend/` — Next.js 16 (App Router, TypeScript, Tailwind),
  deployed to Vercel at `https://frontend-six-khaki-k808d8a0hz.vercel.app`.
  Four tabs, wired to every backend endpoint (see `docs/roadmap.md` for the
  history of what was added when):
  - **Diet** — describe a meal → Gemini estimate → log it; browse any day's
    log (prev/next day + date picker, not just today), delete entries.
  - **Workouts** — exercise catalog + custom exercises, create workouts,
    add/view sets.
  - **Coach** — invite an athlete by email, accept/decline invites, view an
    accepted athlete's logs/workouts read-only.
  - **Profile** — display name, height/weight/BMR/activity level.
  Session handling: a 401 triggers one `supabase.auth.refreshSession()` +
  retry before treating it as a real expiry (signs out with a clear message
  rather than silently failing). All loading states show a "waking up the
  server" message after 4s instead of hanging silently on a Render cold
  start. `npm run build` passes clean. **Still not visually verified in an
  actual browser by Claude** — screenshot automation in this dev environment
  can't reliably capture Chrome (likely opens on the user's second
  monitor) — verification instead comes from curl/API-level testing against
  real throwaway Supabase users each round. Worth the user spot-checking the
  actual UI periodically.

### Backend structure
```
backend/
├── sql/
│   ├── 001_initial_schema.sql   ← full schema + RLS policies, run this first
│   └── 002_seed_exercises.sql   ← small starter exercise catalog
├── app/
│   ├── main.py                  ← FastAPI app, CORS, router wiring
│   ├── core/
│   │   ├── config.py            ← pydantic-settings, reads .env once
│   │   ├── supabase.py          ← client factories (user-scoped + service-role)
│   │   └── auth.py              ← verifies Supabase JWTs against its JWKS endpoint
│   ├── models/                  ← Pydantic schemas, one file per domain
│   └── api/v1/                  ← route handlers, one file per domain
└── requirements.txt
```

### DB schema design (see `backend/sql/001_initial_schema.sql` for the source of truth)
- `profiles` — 1:1 with Supabase's `auth.users`, auto-created via trigger.
  Denormalizes `email` from `auth.users` (which isn't queryable via PostgREST/
  RLS) so coach invites can look athletes up by email.
- `body_metrics` — height/weight/BMR/activity level. Kept separate from
  `profiles` (identity) since it's a different concern that changes
  independently.
- `coach_athlete_links` — `pending` / `active` / `revoked`. **The only source
  of truth for coach access.** A reusable `is_active_coach_of(athlete uuid)`
  SQL function is referenced by every RLS policy that grants a coach
  read-only access to an athlete's data. Coaches never get write access —
  logging is always the athlete's own action.
- `custom_foods`, `food_logs` — per-user food data.
- `exercises`, `workouts`, `workout_sets` — workout tracking. `exercises` is a
  shared catalog (seeded) plus user-added customs.

### Auth design
FastAPI never issues or validates passwords — Supabase Auth does that
entirely from the frontend. `core/auth.py` verifies the JWT Supabase issues
by checking it against Supabase's **JWKS endpoint**
(`/auth/v1/.well-known/jwks.json`) — this is the 2026-current asymmetric-key
approach Supabase recommends, not the older shared-HS256-secret approach.

Route handlers query Supabase using a client scoped to **the caller's own
token** (`get_current_user_client`), not the service-role key — so RLS
applies to every query, including a coach reading an athlete's data. The
service-role client (`get_service_role_client`) exists for the rare case with
no natural "owner" context, and is currently unused (the original plan to use
it for email lookups was replaced by denormalizing `email` onto `profiles`).

## Known gaps / next steps

Phase 0 (rate limiting, CORS lock, pagination, connection pooling, input
caps, three DB-constraint-as-500 bugs) and the core feature set (auth,
AI-estimate-and-log with any-day browsing, workouts, coaching, profile,
session-refresh handling) are done and live on both Render and Vercel — see
`docs/roadmap.md` for the full phase-by-phase plan, what is checked off, and
`docs/accounts.md` for deployment details/gotchas for each service (Supabase
pooler/IPv6, Render health-check routing, Vercel SSO-protected alias).

Remaining known gaps:

1. **No automated tests** (pytest / Playwright). Every round of manual
   stress-testing this project has gone through has found real bugs (a
   Decimal-serialization 500, a self-invite constraint violation, etc.) — a
   test suite would catch regressions between rounds instead of relying on
   repeated manual passes with throwaway Supabase users.
2. **Frontend has not been visually verified in an actual browser by
   Claude** — screenshot automation in this dev environment can't reliably
   capture Chrome (likely because the app opens on the user's second
   monitor). All frontend verification has been `npm run build` +
   curl/direct-API testing against real data, not looking at the rendered
   UI. Worth the user spot-checking the actual UI periodically.
3. Rest of Phase 1 per `docs/roadmap.md` — summary endpoint, edit/delete
   workouts, protected-route redirect on the frontend, loading skeletons,
   weekly calorie chart, PWA manifest.

## Working conventions

- iOS/Swift analogies are genuinely useful when explaining new backend/web
  concepts to the user — they lean on them a lot in `docs/learning-log.md`.
- Supabase has an OAuth-based MCP server (`claude mcp add --transport http
  supabase https://mcp.supabase.com/mcp`, then `/mcp` to authorize — must be
  done in an interactive session, not this non-interactive one). **Render
  does not work this way** — despite Render's docs describing `render mcp
  auth`, that command doesn't exist in the actual CLI (v2.22.0, latest as of
  2026-08-08). Render was instead driven entirely via its own `render` CLI
  (`brew install render`) authenticating non-interactively through
  `RENDER_API_KEY` — no MCP/OAuth involved at all for Render in practice.
  Vercel follows the same non-MCP pattern: `vercel` CLI (`brew install
  vercel-cli`) with `VERCEL_TOKEN`. The `claude` CLI itself had to be
  installed via `npm install -g @anthropic-ai/claude-code` first (it wasn't
  preinstalled) — it lives at `~/.local/nodejs/bin/claude`, not on PATH by
  default. Gemini has no MCP equivalent either; its API key goes directly
  into `.env` / the hosting platform's env vars, never into chat.
- This repo's git remote currently has a personal access token embedded in
  `.git/config` (not committed) for push access — treat that file with the
  same care as a plaintext credential.
- **Commit, push, and deploy iteratively, without asking each time.** The
  user gave standing permission to `git commit` after each meaningful chunk
  of work (2026-08-08), then expanded it (2026-08-10) to cover `git push`
  and redeploying both services too — the full loop for any fix is now:
  fix → test → commit → push → redeploy Render (backend changes) / Vercel
  (frontend changes) → verify live, with no per-step confirmation needed.
  Still split unrelated changes into separate commits rather than one large
  one. This standing permission holds **until the user flags otherwise** —
  it does not automatically extend to other destructive actions not
  explicitly covered (force push, `git reset --hard`, deleting resources,
  etc.) — those still require asking first.
