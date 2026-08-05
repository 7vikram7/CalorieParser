# CalorieParser

A calorie/food and workout tracking app for users and their coaches. Learning
project — see [`docs/learning-log.md`](docs/learning-log.md) for concepts
learned along the way, and [`CLAUDE.md`](CLAUDE.md) for full project context
(architecture, schema design, current status).

## Stack

- **Frontend:** Next.js on Vercel (not started yet)
- **Backend:** FastAPI (Python) on Render
- **Database + Auth:** Supabase (Postgres, Row Level Security, built-in auth)
- **AI:** OpenAI, called server-side from the backend

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
# fill in .env: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY

uvicorn app.main:app --reload
```

API docs available at `http://localhost:8000/docs` once running.

### Database

Run the SQL files in `backend/sql/` against your Supabase project, in order:
1. `001_initial_schema.sql` — tables, triggers, and RLS policies
2. `002_seed_exercises.sql` — a small starter exercise catalog

Either paste them into the Supabase SQL editor, or apply them via the
Supabase MCP server / CLI once connected.
