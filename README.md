# CalorieParser

A calorie/food and workout tracking app for users and their coaches. Learning
project — see [`docs/learning-log.md`](docs/learning-log.md) for concepts
learned along the way, [`docs/roadmap.md`](docs/roadmap.md) for what's planned
next, and [`CLAUDE.md`](CLAUDE.md) for full project context (architecture,
schema design, current status).

**Live app:** https://frontend-six-khaki-k808d8a0hz.vercel.app
**Live API:** https://calorieparser-backend.onrender.com/docs

The backend runs on Render's free tier, which sleeps after 15 minutes idle —
the first request after that can take 30-50s to wake up. The app shows a
"waking up the server" message when this happens; it is expected, not a bug.

## Features

- Email/password auth (Supabase Auth)
- Describe a meal in plain English → AI-estimated calories/macros (Gemini) →
  save it as a custom food → log it against a day
- Browse any day's log, not just today (prev/next day, date picker)
- Workouts: exercise catalog (custom exercises too), workouts, sets
- Coaching: invite an athlete by email, accept/decline invites, a coach can
  view (read-only) an accepted athlete's logs and workouts
- Profile: display name, height/weight/BMR/activity level

## Stack

- **Frontend:** Next.js (App Router, TypeScript, Tailwind) on Vercel
- **Backend:** FastAPI (Python) on Render
- **Database + Auth:** Supabase (Postgres, Row Level Security, built-in auth)
- **AI:** Google Gemini (`gemini-flash-latest`), called server-side from the
  backend — the key never reaches the browser

## Backend — local setup

Requires **Python 3.10+** (`cryptography`, a dependency of `supabase`/`pyjwt`,
has no prebuilt wheel for Python 3.9 and will fail to build).

```bash
cd backend
python3 --version   # confirm 3.10+
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in .env: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
# GEMINI_API_KEY, ALLOWED_ORIGINS

uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs` once running.

### Database

Run the SQL files in `backend/sql/` against your Supabase project, in order:
1. `001_initial_schema.sql` — tables, triggers, and RLS policies
2. `002_seed_exercises.sql` — a small starter exercise catalog

Either paste them into the Supabase SQL editor, or connect directly with
`psql` (see `docs/accounts.md` for the pooler-vs-direct-connection gotcha).

## Frontend — local setup

```bash
cd frontend
npm install
cp .env.example .env.local
# fill in .env.local: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY,
# NEXT_PUBLIC_API_URL (point this at your local backend or the live one above)

npm run dev
```

Open `http://localhost:3000`.
