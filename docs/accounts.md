# Accounts & Services

Tracks which external accounts/services this project uses, and the non-secret
identifiers needed to work with them. Actual secret keys and passwords are
**not here** — see `docs/accounts.secrets.md`, which is gitignored and stays
local-only.

## Supabase
- Project linked to GitHub account: [7vikram7](https://github.com/7vikram7)
- Project URL: `https://wniqdkbfmqqiqzxeqqis.supabase.co`
- Project ref: `wniqdkbfmqqiqzxeqqis`
- Project region: `ap-northeast-1` (relevant for the Session Pooler host,
  `aws-0-ap-northeast-1.pooler.supabase.com` — see
  `docs/accounts.secrets.md` for the full connection string with password).
  The direct-connection host (`db.<ref>.supabase.co`) is IPv6-only with no A
  record, so the pooler is required from networks without IPv6 (e.g. the
  main dev machine, whose VPN only provides link-local IPv6).
- Schema status: **pushed** — `001_initial_schema.sql` and
  `002_seed_exercises.sql` have been applied (8 tables, RLS enabled on all,
  12 seed exercises).
- Anon (public) key — safe to expose in frontend code, access is enforced by
  Row Level Security, not by keeping this secret:
  ```
  eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InduaXFka2JmbXFxaXF6eGVxcWlzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODYxODQ5NjAsImV4cCI6MjEwMTc2MDk2MH0.1RB4MHSbGmOTN8CTmKJgkAYSk0L6w0Wiy-U-A2EwPr4
  ```
- Publishable key (newer-format equivalent of the anon key, also safe to
  expose):
  ```
  sb_publishable_8MK0lhxo3aQ0WYS9D0Thpw_Q3gNaE-p
  ```

### CLI setup
```bash
supabase login
supabase init
supabase link --project-ref wniqdkbfmqqiqzxeqqis
```

## GitHub
- Repo: https://github.com/7vikram7/CalorieParser

## Render
- Web service: `calorieparser-backend` (id `srv-d9rktb49v7es73chpfsg`), workspace
  `My Workspace` (`tea-d9rk0rf40ujc73bm8b40`).
- Live URL: `https://calorieparser-backend.onrender.com` — deployed
  2026-08-08 from `backend/` (root dir), branch `main`, free plan, region
  `oregon`, runtime `python`, build `pip install -r requirements.txt`, start
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Env vars set: `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY` (same values as
  `backend/.env` / `docs/accounts.secrets.md`).
- Verified working: `/docs` → 200, unauthenticated `/v1/profiles/me` → 401
  (real JWT verification against Supabase JWKS, not a stub).
- **`/health` returns 404 when hit externally — this is expected, not
  broken.** Render reserves the exact path passed to `--health-check-path`
  for its own internal load-balancer probing (confirmed via `render logs`:
  internal IPs get 200 on `/health` every 5s, external requests never reach
  the app at all, edge answers with `x-render-routing: no-server` first).
  Don't "fix" this — it doesn't mean the app is unhealthy.
- CLI: `render` (installed via `brew install render`), authenticates
  non-interactively via `RENDER_API_KEY` env var (no OAuth/MCP needed — the
  `render mcp auth` command described in Render's docs doesn't exist in CLI
  v2.22.0, the latest as of 2026-08-08).

## Vercel
- Account: `vikram-gore` (Hobby team) / personal account `7vikram7` — see
  `docs/accounts.secrets.md` for the API token.
- Project: `frontend` (deploys `frontend/` from this repo).
- Live URL: `https://frontend-six-khaki-k808d8a0hz.vercel.app` — deployed
  2026-08-09 via `vercel deploy --prod` (CLI, `VERCEL_TOKEN` env var,
  non-interactive). Verified: 200, correct page title, initial client-render
  state present.
- **The shorter alias `https://frontend-vikram-gore.vercel.app` 302s to
  Vercel's own SSO login (`vercel.com/sso-api`) — this is Vercel's
  Authentication protection on that particular alias, not an app problem.**
  Use the URL above (or `https://frontend-7vikram7-vikram-gore.vercel.app`,
  also unprotected) instead. If a custom domain is added later, check
  Project Settings → Deployment Protection if this recurs.
- Env vars set (Production, Preview, Development — all marked
  non-sensitive since they're `NEXT_PUBLIC_*` and meant to reach the
  browser): `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `NEXT_PUBLIC_API_URL` (points at the Render backend).
- CLI: `vercel` (installed via `brew install vercel-cli`), authenticates
  non-interactively via `--token` / `VERCEL_TOKEN` — same pattern as Render,
  no MCP/OAuth needed.

## Google Gemini
- Used for `POST /v1/foods/estimate` (replaced the original OpenAI plan —
  Gemini's free tier needs no billing), model `gemini-flash-latest` — the
  pinned `gemini-2.0-flash` lost free-tier quota by 2026-08, so the code
  uses the rolling `-latest` alias instead, currently resolving to
  `gemini-3.7-flash`.
- **Real free-tier limit (found 2026-08-14 via an actual 429 response, not
  from Google's docs):** `GenerateRequestsPerDayPerProjectPerModel-FreeTier`
  = **20 requests/day** for `gemini-3.7-flash`. Earlier notes here said
  "15 RPM, 1M tokens/day" — that was never verified against a real quota
  error and turned out to be wrong; the actual constraint is per-day, not
  per-minute, and far more restrictive. Local dev and production share this
  quota (same `GEMINI_API_KEY`), so heavy local testing can exhaust the
  live app's daily budget too — confirmed firsthand while building Phase 3a
  tool-use, see `docs/roadmap.md`/`docs/agent-architecture-plan.md`.
- API key created at: https://aistudio.google.com/apikey
- Key value lives in `backend/.env` (`GEMINI_API_KEY`) and
  `docs/accounts.secrets.md` — not here.
