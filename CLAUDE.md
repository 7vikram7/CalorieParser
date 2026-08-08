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
| Frontend | Next.js | Vercel | Not started yet |
| Backend | FastAPI (Python) | Render | Railway's free tier is gone (removed 2023); Render still has one. FastAPI kept as a separate service (not Next.js API routes) specifically so a future mobile app can call the same API. |
| DB + Auth | Supabase (Postgres) | Supabase | BaaS pattern: frontend reads directly from Supabase where possible; FastAPI only handles secrets/AI/complex logic. Auth is 100% Supabase's — FastAPI never issues tokens, only verifies them. |
| AI | Google Gemini (`gemini-flash-latest`) | called from FastAPI | Server-side only — key must never reach the browser. Switched from the original OpenAI plan specifically for the free tier: 15 RPM, 1M tokens/day, no billing required. Uses the `-latest` alias, not a pinned version — `gemini-2.0-flash` lost free-tier quota by 2026-08, so pinning is riskier than tracking Google's current recommended flash model. |

## Current status (as of 2026-08-08)

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
- No frontend code exists yet.

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

1. **Supabase schema is pushed (2026-08-08).** Done via `psql` (installed
   via `brew install libpq`, binary at `/usr/local/opt/libpq/bin/psql`)
   against the Supavisor pooler — see `docs/accounts.md`/`accounts.secrets.md`
   for the connection string. The Supabase MCP server is registered but still
   needs OAuth authorization in an interactive session (`/mcp`) if MCP-based
   access is wanted later; it wasn't needed for this push.
2. **`POST /v1/foods/estimate` is done and verified working** against a real
   Gemini call (`GEMINI_API_KEY` is set in `backend/.env` and
   `docs/accounts.secrets.md`) — normal input returns a correct structured
   estimate, vague input correctly returns `confidence: 0.0` with a note
   instead of guessing, empty input returns 422. This is the one part of the
   backend actually confirmed working end-to-end against real external
   services so far.
3. **Local Python must be 3.10+.** Discovered the hard way: the original dev
   machine's default `python3` was 3.9.5 (EOL), and `cryptography` (a
   transitive dep of `supabase`/`pyjwt[crypto]`) has no prebuilt wheel for it,
   so `pip install` failed without a Rust toolchain. Fixed by installing
   Python 3.12 via Homebrew (`/usr/local/bin/python3.12`) — use that (or newer)
   to create `backend/.venv`, not the system `python3`.
4. **Render hosting not set up yet** — needs this repo to exist first (done)
   and Supabase env vars to exist (step 1) before it's useful to connect.
5. **No frontend yet.** Vercel/Next.js setup is intentionally deferred until
   backend basics are working end-to-end.

## Working conventions

- iOS/Swift analogies are genuinely useful when explaining new backend/web
  concepts to the user — they lean on them a lot in `docs/learning-log.md`.
- MCP servers for Supabase, Render, and Vercel all support OAuth-based
  connection in Claude Code (`claude mcp add --transport http <name> <url>`,
  then `/mcp` to authorize) — no manual token-pasting needed for those three.
  The `claude` CLI itself had to be installed via `npm install -g
  @anthropic-ai/claude-code` first (it wasn't preinstalled) — it lives at
  `~/.local/nodejs/bin/claude`, not on PATH by default. Gemini/OpenAI have no
  MCP equivalent; their API key goes directly into `.env` / the hosting
  platform's env vars, never into chat.
- This repo's git remote currently has a personal access token embedded in
  `.git/config` (not committed) for push access — treat that file with the
  same care as a plaintext credential.
