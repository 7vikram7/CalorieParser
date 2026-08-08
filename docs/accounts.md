# Accounts & Services

Tracks which external accounts/services this project uses, and the non-secret
identifiers needed to work with them. Actual secret keys and passwords are
**not here** — see `docs/accounts.secrets.md`, which is gitignored and stays
local-only.

## Supabase
- Project linked to GitHub account: [7vikram7](https://github.com/7vikram7)
- Project URL: `https://wniqdkbfmqqiqzxeqqis.supabase.co`
- Project ref: `wniqdkbfmqqiqzxeqqis`
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
- Not yet created.

## Vercel
- Not yet created.

## Google Gemini
- Used for `POST /v1/foods/estimate` (replaced the original OpenAI plan —
  Gemini's free tier needs no billing: 15 RPM, 1M tokens/day, model
  `gemini-flash-latest` — the pinned `gemini-2.0-flash` lost free-tier quota
  by 2026-08, so the code uses the rolling `-latest` alias instead, currently
  resolving to Gemini 3.6).
- API key created at: https://aistudio.google.com/apikey
- Key value lives in `backend/.env` (`GEMINI_API_KEY`) and
  `docs/accounts.secrets.md` — not here.
