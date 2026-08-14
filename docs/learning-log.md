# CalorieParser — Learning Log
> Concepts learned during build sessions. Structured high → low level.
> Updated progressively as new topics come up.

---

## LEVEL 1 — Architecture (The Big Picture)

### What is Backend as a Service (BaaS)?
Traditional apps route every request through an app server, even simple reads.
BaaS (like Supabase) lets the frontend talk directly to the database for reads,
so the app server only handles logic that truly needs a trusted environment.

```
Old way:   Frontend → App Server → Database → App Server → Frontend
BaaS way:  Frontend → Supabase (direct reads)
          Frontend → App Server (AI, secrets, complex logic only)
```

### Our Stack at a Glance
| Layer        | Technology       | Hosted on       |
|--------------|------------------|-----------------|
| Frontend     | Next.js (React)  | Vercel          |
| Backend API  | FastAPI (Python) | Railway / Render|
| Database+Auth| PostgreSQL       | Supabase        |

---

## LEVEL 2 — Hosting Platforms

### Vercel
- An **application host** — hosts the compiled Next.js app and delivers it to users' browsers globally via a CDN.
- Think of it as: Supabase stores the *data*, Vercel serves the *application* (HTML, CSS, JS).
- Without Vercel: users have no app to look at. Without Supabase: the app has no data to show.
- Also supports serverless functions (short-lived, stateless JS/TS code).
- Cannot run persistent Python servers like FastAPI — functions time out too quickly.
- Role in this project: serves the Next.js web app to users' browsers.

### Railway
- Platform as a Service (PaaS) for backend servers.
- You push code, Railway detects the language and builds it automatically.
- Runs on AWS under the hood — you never interact with AWS directly.
- Good for: small-to-medium backends, fast setup, usage-based pricing.
- Role in this project: runs the FastAPI Python server.

### Render
- Similar to Railway — another PaaS abstraction over cloud providers.
- Slightly more configuration options, has a free tier (server sleeps when idle).
- Role in this project: alternative to Railway for hosting FastAPI.

### Why not Vercel for FastAPI?
Vercel functions are serverless and stateless with a hard time limit (~60s).
FastAPI uses uvicorn — a persistent process that stays running. They are incompatible.

---

## LEVEL 3 — Database & Security

### Supabase
- Managed PostgreSQL database with extras bolted on:
 - REST API (via PostgREST) — query your DB over HTTP without writing SQL
 - Authentication system built in
 - Real-time subscriptions
 - Storage (file uploads)
- Not a new database — it's PostgreSQL underneath with tooling on top.

### Row Level Security (RLS)
- A PostgreSQL feature (not Supabase-specific, but Supabase makes heavy use of it).
- Security rules written directly in the database, not in application code.
- Example: "a user can only SELECT rows where user_id = their own ID"
- Why it matters: even if a developer forgets a WHERE clause, the DB still blocks it.
- Industry practice: increasingly common, especially when frontends talk directly to DBs.

```sql
-- Example RLS policy
CREATE POLICY "users see own logs"
ON daily_food_logs FOR SELECT
USING (auth.uid() = user_id);
```

### Supabase Anon Key
- A JWT token that identifies the caller as an anonymous/public role.
- Safe to embed in frontend code — it only works within RLS rules.
- If stolen, it still cannot access another user's data (RLS blocks it).
- Not a PostgreSQL concept — it's Supabase + PostgREST layered on top of Postgres.

### Supabase Service Role Key
- A JWT token with superuser privileges — bypasses all RLS.
- Must NEVER reach the browser or be committed to Git.
- Lives only in the FastAPI backend environment.
- Used for admin operations: creating user profiles, cross-user queries, background jobs.

### Supabase Auth
- Supabase ships a complete auth system (no need to build it):
 - Sign up / login / logout
 - JWT issuance and refresh
 - Magic links, OAuth (Google, GitHub), OTP
- In this project: registration and login happen directly from Next.js → Supabase Auth.
- FastAPI is NOT involved in auth — it only verifies the JWT Supabase already issued.

---

## LEVEL 4 — Backend (FastAPI / Python)

### Flask vs Django vs FastAPI — What Are They?
All three are Python web frameworks — they handle HTTP requests and help you build APIs.

| | Flask | Django | FastAPI |
|---|---|---|---|
| Philosophy | Minimal, add what you need | Batteries included | Modern, fast, async-first |
| Ships with | Almost nothing | ORM, admin, auth, forms | Validation, auto-docs |
| Structure | You decide | CLI generates it | You decide (app/ convention) |
| Best for | Simple APIs, microservices | Full web apps with admin UI | High-performance APIs + AI |
| Swift analogy | URLSession (raw) | SwiftUI + CoreData (opinionated) | Combine + Codable (modern) |

FastAPI came after Flask and Django, learning from their limitations.
It adds async support, automatic input validation, and auto-generated Swagger docs.

### What is Pydantic?
A Python **data validation library** — not built into Python, third-party.
You define a class describing the shape of your data; Pydantic enforces it at runtime.

```python
class FoodEstimateRequest(BaseModel):
   description: str  # Pydantic rejects anything that isn't a string
```

FastAPI is built entirely on Pydantic — every request body, response model, and
config object in this project is a Pydantic model. This gives us:
- Automatic input validation (bad requests rejected before your code even runs)
- Auto-generated /docs Swagger UI
- Type safety in the IDE

`pydantic-settings` is a Pydantic extension specifically for reading `.env` files
into typed classes. Not a Python standard — the most popular FastAPI convention.

### Python Decorators — @router.post and @app.get
The `@` syntax is a core **Python language feature** called a decorator.
It is NOT FastAPI-specific. Swift equivalent: property wrappers (`@State`, `@Published`).

```python
@router.post("/estimate", response_model=FoodEstimateResponse)
async def estimate_food(payload: FoodEstimateRequest):
   ...
```

Reading it: *"register the function below as a POST handler for /estimate, and
validate the response against FoodEstimateResponse."*
The function `estimate_food` still exists normally — the decorator just attaches
metadata/behaviour to it without changing the function itself.

`async def` means the function is asynchronous — it can pause mid-execution (e.g.
while waiting for OpenAI to respond) and let other requests be processed.
FastAPI is built around async natively; this is why it is faster than Flask.

### Middleware — Intercepts Every Request/Response
Your Node.js mental model is exactly right. Middleware sits between uvicorn and
your route handlers:

```
Request → [CORSMiddleware] → [AuthMiddleware (future)] → Route Handler → Response
```

**CORS (Cross-Origin Resource Sharing)**
A browser security rule: JavaScript cannot call an API on a different domain than
the current page. Our Next.js app (`calorieparser.vercel.app`) calling FastAPI
(`calorieparser.railway.app`) would be blocked by the browser by default.

`CORSMiddleware` intercepts every response and adds headers:
```
Access-Control-Allow-Origin: *
```
...telling the browser this server permits cross-domain calls.

`allow_origins=["*"]` — any domain allowed. Fine for development.
In production: replace `*` with `"https://calorieparser.vercel.app"` only.

### FastAPI vs uvicorn — The iOS Analogy
| iOS | Our Stack | Role |
|---|---|---|
| `URLSession` | FastAPI | Handles HTTP request/response objects — routes, payloads, validation, return values |
| iOS TCP/IP network stack | uvicorn | Sits at the port, listens for raw TCP connections, speaks HTTP protocol, hands parsed requests to FastAPI |

You never think about TCP in iOS — `URLSession` abstracts it.
FastAPI developers never think about socket listening — uvicorn abstracts it.
FastAPI is the "what to do", uvicorn is the "how to receive it".

### .env and python-dotenv — Loaded Once, Not Per File
Common misconception: you do NOT import dotenv in every file that needs a setting.
The `.env` file is read exactly once when the app starts, in `config.py`:

```python
class Settings(BaseSettings):
   model_config = {"env_file": ".env"}  # read once at startup

settings = Settings()  # triggers the .env read — singleton pattern
```

Then any file imports the already-loaded object:
```python
from app.core.config import settings
print(settings.SUPABASE_URL)  # no re-reading .env, just a Python object
```

This is the same pattern as a singleton in iOS — initialised once, referenced
everywhere. The `settings` object lives in memory for the lifetime of the process.

### Django — Does It Render Frontend Too?
Yes. Django has a built-in templating engine — you write HTML templates, Django fills
them with data on the server, and sends complete HTML to the browser.
This is called Server-Side Rendering (SSR).

Comparison to the Salesforce analogy:
| | Django | Salesforce / WordPress |
|---|---|---|
| UI driven by | Your Python code + HTML templates | Portal config, drag-drop |
| Customisation | Unlimited — pure code | Limited to platform features |
| Who builds it | Developers writing code | Non-developers via config |

In modern development most teams use Django only as a backend API (like FastAPI)
and pair it with React/Next.js for the frontend — because client-side React gives
a richer UX than server-rendered HTML pages.

### /docs — Auto-Generated From Code, Not Just Comments
FastAPI generates the Swagger UI at /docs from three sources simultaneously:

1. **Pydantic model field names + types** → appear as request/response schemas
2. **Decorator metadata** (`@router.post("/estimate", response_model=...)`) → HTTP method, path, expected response
3. **Docstrings** (the text inside triple quotes in a function) → endpoint description

No extra configuration needed. Zero lines of documentation code written by us.

### Schemas Split Into Domain Files (Refactored)
All models have been split from one `schemas.py` into domain-specific files.
Rule of thumb: split when a file exceeds ~150-200 lines OR a domain grows its own complexity.

```
app/models/
├── schemas.py      ← now a backward-compatible re-export file only
├── user.py         ← UserBase, UserCreate, UserResponse
├── profile.py      ← UserProfileCreate, UserProfileUpdate, UserProfileResponse
├── food.py         ← UserCustomFoodCreate, UserCustomFoodResponse
├── log.py          ← DailyFoodLogCreate, DailyFoodLogResponse
└── estimation.py   ← FoodEstimateRequest, NutritionalEstimate, FoodEstimateResponse
```

`schemas.py` is kept as a re-export file so any code that still imports from it
doesn't break — it simply re-exports everything from the new files.
New code should import directly from the domain file (e.g. `from app.models.food import ...`).

### CORS — Why Browsers Block Cross-Domain Requests
**The Problem:**
Imagine you are on `evil.com`. That page's JavaScript tries to call
`https://yourbank.com/api/transfer?to=hacker`. Without CORS restrictions,
the browser would send your bank session cookie with that request — the bank's
server would think it was you. This is called a **Cross-Site Request Forgery (CSRF)** attack.

**The Browser's Defence:**
Browsers enforce a rule called the **Same-Origin Policy**:
JavaScript on `domain-a.com` cannot make requests to `domain-b.com` by default.
"Origin" = scheme + domain + port. Any difference is cross-origin.

**The Problem This Creates For Us:**
Our Next.js app runs on `calorieparser.vercel.app`.
Our FastAPI runs on `calorieparser.railway.app`.
Different domains → browser blocks the call.

**How CORS Fixes It (Server Permission System):**
The server opts in to allow specific origins by adding response headers:
```
Access-Control-Allow-Origin: https://calorieparser.vercel.app
```
The browser sees this header and allows the JavaScript call to proceed.

```python
# Our main.py — the server tells browsers who is allowed to call it
app.add_middleware(
   CORSMiddleware,
   allow_origins=["*"],   # "*" = anyone (dev only)
)
```

`"*"` means any domain can call our API. Safe for local development.
In production: replace with `["https://calorieparser.vercel.app"]` only.

Key insight: CORS is enforced by the **browser**, not the server.
Direct API calls (curl, Postman, server-to-server) are never blocked by CORS —
only browser JavaScript is affected. This is why the /docs page works fine locally.

### How Much uvicorn Code Did We Write?
**Zero lines.** We never imported or configured uvicorn in any Python file.

uvicorn is only referenced in the terminal command to start the server:
```bash
uvicorn app.main:app --reload
```

- `app.main` → the Python file path (`app/main.py`)
- `app` → the FastAPI instance variable name inside that file
- `--reload` → restart automatically when any `.py` file changes (dev only)

That is the entire uvicorn integration. FastAPI handles everything else.
This is by design — the framework and the server are deliberately decoupled.
You could swap uvicorn for `gunicorn` or `hypercorn` by changing only that one command.
Next.js has server-side capabilities (API Routes, Server Actions) that could handle
simple logic. FastAPI is used here because:
1. OpenAI key must stay server-side — both approaches handle this.
2. Python's AI/ML ecosystem is far richer than Node.js (LangChain, NumPy, etc.).
3. The FastAPI service can be called by mobile apps later — not tied to Next.js.
If there were no AI component, Next.js alone + Supabase would likely be sufficient.

### Next.js API Routes vs Server Actions (clarification)
These are NOT just client-side HTTP requests. They run on Vercel's server:
- API Routes: files at `app/api/route.ts` that become HTTP endpoints.
- Server Actions: functions marked `"use server"` called directly from React components.
 React calls them directly — no explicit `fetch()` needed, the HTTP happens invisibly underneath.
Both run server-side — secrets are safe. But they are JavaScript/TypeScript, not Python.

### Why Not Just Run Everything in the Browser?
Three hard blockers — not preference, actual technical constraints:

**1. Secrets cannot live in browser code**
If you put your OpenAI API key in JavaScript that runs in the browser, anyone can open
DevTools → Sources and read it. Server-side code keeps secrets off the client entirely.

**2. The browser cannot be trusted**
A user could open DevTools and modify any JavaScript running on their machine before
it executes. Any validation or business logic client-side can be bypassed.
Server-side code runs in an environment the user has zero access to.

**3. Direct database access from the browser is dangerous**
Raw Postgres never accepts browser connections. Supabase solves this via its API layer
+ RLS, but there are still limits on what an anonymous browser caller can do.

The browser is good for: rendering UI, local state (forms, animations), calling APIs
and displaying the response. Everything involving secrets or trust must leave the browser.

### How FastAPI Knows a Request is Authenticated
1. User logs in → Supabase issues a JWT to the Next.js frontend.
2. Frontend attaches JWT to every FastAPI request: `Authorization: Bearer <token>`
3. FastAPI middleware decodes and verifies the JWT signature.
4. If valid, extracts user_id from the token payload.
5. Uses that user_id for all subsequent DB operations.
Not yet implemented in this scaffold — planned for Step 3.

### LangChain
- Python framework for building LLM-powered applications.
- Provides abstractions for: prompt templates, chaining multiple AI calls,
 memory (conversation history), agents (AI that decides which tools to call),
 retrieval (searching a knowledge base before prompting).
- Relevant here: could be used to build a smarter food estimation pipeline
 e.g., search a nutrition database first, then ask the LLM to reason over results.

### NumPy
- Python library for numerical computing.
- Relevant for nutrition tracking: calculating TDEE, weighted averages of macros,
 statistical summaries of eating patterns over time.
- Less critical for the MVP — more useful if the app grows into trend analysis.

---

## LEVEL 5 — Project Folder Structure

### The `app/` parent folder — is it a Python standard?
Not a hard rule, but it is the widely adopted convention for FastAPI and most Python
web frameworks. The idea: all your application source code lives inside one named
folder (`app/`), keeping it separate from config files at the repo root
(`requirements.txt`, `.env`, `README.md`).

Equivalent conventions in other ecosystems:
| Ecosystem | Source folder convention |
|-----------|--------------------------|
| FastAPI / Flask | `app/` |
| Django | the project package (e.g. `myproject/`) |
| Node.js / Express | `src/` |
| Next.js | `app/` or `src/app/` |
| Swift / iOS | the target folder named after the app |

So yes — seeing an `app/` folder in a Python web project is a reliable signal
that the developer followed standard layout conventions.

### The sub-folders inside `app/`

```
app/
├── main.py          ← entry point
├── core/            ← cross-cutting concerns (config, DB connection, auth helpers)
├── models/          ← data shapes (Pydantic schemas)
└── api/
   └── v1/          ← versioned route handlers
       └── foods.py
```

**`core/`** — things every other module needs:
- `config.py` reads `.env` and exposes a typed `settings` object
- Future additions: Supabase client singleton, JWT verification helper

**`models/`** — pure data definitions with no logic:
- `schemas.py` defines what requests/responses look like (Pydantic models)
- Future additions: separate files per domain (e.g. `user.py`, `food.py`)

**`api/v1/`** — the actual HTTP route handlers, grouped by version:
- `v1` subfolder means if you ever break the API contract, you create `v2/`
 and old clients keep working against `v1` — nothing breaks
- Each file groups related endpoints (e.g. `foods.py`, `users.py`, `logs.py`)

### What is `__init__.py`?
An empty file that tells Python: *"treat this folder as a package"* (i.e. importable module).
Without it, `from app.core.config import settings` would fail — Python wouldn't
recognise `app`, `core`, or `models` as importable namespaces.
- You don't write any code in them for a standard layout like ours
- Every folder that needs to be imported must have one
- No equivalent in Node.js — all folders are automatically importable there

### What is `__pycache__/`?
Auto-generated by Python at runtime — you never create or edit it.
When Python first imports a `.py` file it compiles it to bytecode (`.pyc`) and
caches it here so the next import is faster (skips re-parsing the source).
- Safe to delete at any time — Python recreates it on the next run
- Always listed in `.gitignore` — never committed to the repo
- Equivalent to the compiled `.class` files in Java, or the `.o` object files in C

---

## LEVEL 5b — Project Files & Python Tooling

### Is main.py a Python standard or FastAPI-specific?
`main.py` as the entry point is a **Python-wide convention** — Flask, plain scripts,
and CLI tools all use it. FastAPI does not enforce the name; it's just tradition.
The `app/` folder layout however IS a FastAPI convention, recommended in FastAPI's
own documentation. Other frameworks differ:

| Framework | Layout style                          | How you start               |
|-----------|---------------------------------------|-----------------------------|
| FastAPI   | `app/` folder, you design structure   | `uvicorn app.main:app`      |
| Django    | CLI generates a fixed structure       | `python manage.py runserver`|
| Flask     | No enforced structure                 | `flask run`                 |
| Express   | `src/` convention, no enforcement     | `node src/index.js`         |

### What is imported in each file and why?

**main.py**
```python
# (entry unfinished as of this point in the log — picking back up below)
```

---

## LEVEL 6 — Deploying to Production

### Getting the schema onto a real database
`backend/sql/001_initial_schema.sql` sat unrun for a while — having SQL
files in the repo is like having a `.xcdatamodeld` file that was never
added to a target: the shape is defined, but nothing's actually built from
it. Running it against Supabase's Postgres (via `psql`) is the migration
step, equivalent to Core Data actually creating the SQLite store from your
model on first launch.

### Why the "obvious" connection string didn't work
Supabase gives you a direct connection string like
`db.<ref>.supabase.co:5432`. On a network without IPv6, this fails outright
— that hostname only has an `AAAA` (IPv6) DNS record, no `A` (IPv4) record.
This is a real, increasingly common gotcha as providers roll out IPv6-only
infrastructure to save IPv4 address costs.

The fix: Supabase also runs a **connection pooler** (Supavisor) reachable
over IPv4, at `aws-0-<region>.pooler.supabase.com`. Same database, different
front door — think of it like your app almost always talking to CloudKit's
public endpoint, but there being a lower-level direct path that only works
under specific network conditions.

One wrinkle: the pooler is shared across many projects in a region, so the
username changes from `postgres` to `postgres.<project-ref>` — the ref is
how the shared pooler knows *which* project's database you mean. Not
knowing the project's region up front, this got found by brute-force
probing every AWS region's pooler hostname until one authenticated instead
of returning "tenant not found."

### Deploying a backend: Render, via CLI, not a dashboard click
Render (like most modern hosts) has both a web dashboard and a CLI/API. The
CLI can fully create a service, set environment variables, and trigger a
deploy — no browser required. This matters for anything scripted or
automated (CI, or an AI agent driving the process): a `RENDER_API_KEY`
environment variable is enough to authenticate non-interactively, similar
to how a CI pipeline authenticates to App Store Connect with an API key
rather than an interactive Apple ID login.

**Health checks are internal, not public.** Render (and most PaaS hosts)
pings your app's health-check path from inside their own network to decide
if an instance is alive — that's a different, private request path from
what the public internet sees. Hitting the same path from outside can 404
by design; it doesn't mean the app is broken. This is analogous to an
iOS app's background health/heartbeat ping vs. a real user opening the app.

### Deploying a frontend: Vercel, same CLI pattern
Vercel's CLI follows the identical non-interactive pattern: a personal
access token via a `VERCEL_TOKEN` environment variable, no browser needed.
Once a project is linked, `vercel deploy --prod` builds and ships it.
Environment variables prefixed `NEXT_PUBLIC_` are intentionally shipped to
the browser (Next.js bakes them into the client bundle) — the opposite of
a secret. That's the correct, expected place for things like a Supabase
anon key, which is meant to be public and relies on Row Level Security for
protection rather than secrecy (see LEVEL 3).

### OAuth vs. API tokens — and why an AI agent can't do OAuth for you
Some platforms (Supabase, in this project) offer an OAuth-based MCP
connection: your coding assistant opens a browser, you log in and click
"Allow," and the assistant gets access. This is *by design* un-automatable
— OAuth's entire purpose is to guarantee a human explicitly consents before
an app gets access to an account. No amount of CLI cleverness should ever
bypass that consent screen; that's the security boundary working as
intended, not a limitation to route around.

Render and Vercel, in practice, turned out to skip MCP/OAuth entirely for
this kind of scripted setup and instead use a plain API token — closer to
how you'd generate an App Store Connect API key than how you'd sign in
with "Continue with Google."

---

## LEVEL 7 — Hardening a Public API

A "pressure test" of the working backend surfaced six real gaps — the kind
that don't show up until you deliberately ask "how would this break in
production?" rather than "does the happy path work?"

### Rate limiting: protecting a metered dependency, not just the server
`/v1/foods/estimate` costs real Gemini API quota on every call, and (at the
time) had no auth requirement at all — anyone could hit it as fast as they
wanted. Added `slowapi` (a FastAPI-flavored wrapper around the `limits`
library) with a **tiered limit**: 5/minute for anonymous callers (keyed by
IP), 15/minute for authenticated ones (keyed by user ID, decoded from
whatever bearer token is present — falling back to IP if the token is
missing or garbage). This is the backend equivalent of an iOS app
debouncing a network call so a user mashing a button doesn't fire 50
requests — except here it's enforced server-side, since you can't trust a
client to self-limit.

### Locking down CORS: an allowlist is not paranoia, it's the default
`ALLOWED_ORIGINS=["*"]` (or an unset default that resolves to it) means
literally any website can call your API from a user's browser and have the
browser attach their cookies/session. Locking it to the exact origins that
should be allowed — the real Vercel URL and `localhost:3000` for local dev
— is table stakes, not an optimization. Nothing about this affects
non-browser clients (curl, a native app, server-to-server calls) — CORS is
a browser-enforced restriction, not a server-side auth mechanism.

### The `"now()"` string bug — a subtle type trap
`coaches.py` had `.update({"responded_at": "now()"})` — sending the
*literal 4-character string* `"now()"` to Postgres, not the SQL keyword. In
raw SQL, `now()` unquoted is a function call; `'now()'` as a string
literal is just text that fails to parse as a timestamp. The fix:
compute the actual timestamp in Python (`datetime.now(timezone.utc)`,
not the deprecated `datetime.utcnow()`) and send a real ISO 8601 value.
The bug was easy to miss because tests-by-inspection ("does this look like
it sets a timestamp?") don't catch it — only actually calling the endpoint
against a real database would.

### Pagination: `.range()`, not `.slice()`
Supabase/PostgREST's Python client uses `.range(start, end)` — both ends
**inclusive** — backed by HTTP `Range` headers under the hood, not a
`LIMIT`/`OFFSET` SQL string you write yourself. `limit=50, offset=100`
becomes `.range(100, 149)`. Without any cap, a list endpoint will happily
try to return every row a user has ever created in one response — fine at
10 rows, a real problem at 100,000. `ge=1, le=200` on the `limit` query
param (via Pydantic's `Field`/`Query` validation) also stops a caller from
requesting an absurdly large page size in the first place.

### Reusing the HTTP connection pool
`create_client()` (Supabase's client constructor) opens a fresh
`httpx.Client` — and therefore a fresh TCP + TLS handshake — every time
it's called. Since a new client was being created **on every single
request**, that handshake cost was being paid constantly instead of once.
The fix: create one shared `httpx.Client()` at import time and pass it into
every `create_client()` call via `SyncClientOptions(httpx_client=...)`, so
every request reuses the same warm connection pool. This is safe under
concurrency specifically because `.postgrest.auth(token)` sets a header on
the *per-request* Postgrest client wrapper (`self.headers`), not on the
shared `httpx.Client` itself — so two concurrent requests never leak each
other's auth token even though they share a connection pool underneath.
Conceptually similar to `URLSession.shared` vs. creating a brand new
`URLSession` per network call in iOS.

---
from fastapi import FastAPI   
## LEVEL 8 — Agentic AI, Part 1: Function Calling

The first real "agent" step for `/v1/foods/estimate` (Phase 3a): giving
Gemini a tool it can call mid-conversation, instead of answering purely
from its own training data.

### What "function calling" actually means
You describe a function to the model (name, description, parameter schema)
without giving it real code to run. The model can't execute anything itself
— when it decides a tool would help, it replies with *a request to call
that function* (name + arguments) instead of a normal answer. Your backend
is the one that actually runs the real code (here: a USDA FoodData Central
API search), then hands the result back to the model in a follow-up message
so it can finish answering with real data instead of a guess. The model
never touches the network itself — this is the opposite of it being handed
credentials and going off on its own.

### The two-call constraint
Gemini won't let you ask for both "you may call a tool" and "respond in
strict JSON" in the same request — function calling and structured output
mode are mutually exclusive per call. So a tool-using turn is always at
least two round trips: turn one offers the tool and gets back either a
function-call request or a plain-text answer; turn two (with the tool
removed and the function's result appended to the conversation, if there
was one) asks for the final structured JSON. This is why `_estimate_grounded()`
in `foods.py` looks like two separate `generate_content` calls sharing one
growing `contents` list, not one call with extra config.

### AUTO mode: the model decides for itself whether to bother
Passing a tool doesn't force the model to use it. With
`function_calling_config.mode = "AUTO"`, Gemini decides per-request whether
looking something up is worth it — a well-known single food might get
answered directly, while "dal rice with papad and pickle" got split into
four separate parallel tool calls (one per component) before Gemini
answered. This is exactly the "soft routing" a much heavier router
component could do explicitly — sometimes the model doing its own judgment
call is enough.

### The quota surprise: free tier limits are not what the docs implied
This project's own docs said Gemini's free tier was "15 RPM, 1M
tokens/day" — a number carried forward from early setup and never actually
tested against a real quota error. Building this feature hit a real `429`
that revealed the actual constraint:
`GenerateRequestsPerDayPerProjectPerModel-FreeTier` = **20 requests per
day**, period — not a per-minute throughput limit at all. Two lessons:

1. **A documented limit you haven't personally triggered is a guess, not a
   fact.** The 15 RPM figure sounded authoritative because it was written
   down, but nobody had actually exhausted the quota to check.
2. **Doubling a call count is not free just because each call is "free
   tier."** The tool-calling flow costs 2 Gemini calls per estimate instead
   of 1. Applying that to every request would have roughly halved the
   app's entire daily capacity for logging a meal at all - the app's most
   basic feature. The fix was a cheap heuristic gate (`_needs_grounding()`)
   that keeps simple, obviously-easy descriptions on the original 1-call
   path and only pays for tool-augmented grounding on multi-item or long
   descriptions where it's actually likely to help. This is a tiny slice of
   the "Phase 3b: routing" idea that was originally planned for *later* -
   the quota math forced part of it into 3a instead. Sometimes a plan's
   phase boundaries are aspirational until reality (a quota, in this case)
   moves the line for you.

### Retries can make an outage feel like a hang, not a failure
Gemini's SDK retries failed requests automatically - by default, 5 attempts
with exponential backoff up to 60 seconds between them. That's reasonable
in isolation, but it means a single "model is experiencing high demand"
503 can silently turn into minutes of a request just sitting there instead
of failing fast. Tightened to 2 attempts / 3s max delay per call here -
worth remembering for any SDK with its own retry logic layered under yours:
check what it does by default before assuming a hang means your code is
broken.

## LEVEL 9 — Agentic AI, Part 2: Multiple Providers, Caching, and a Real Bug in the Fallback

Phase 3b, built the same day as Level 8 once the 20-req/day Gemini quota
made it clear Gemini alone couldn't carry the app's core feature.

### A provider abstraction is just "don't let the route handler know which vendor it's talking to"
Before this, `foods.py` imported `google.genai` directly and built Gemini's
request objects inline. That's fine with one provider, but adding a second
one (Groq) the same way would have meant `foods.py` branching on which SDK
to call, with two different exception shapes, two different client
constructors, two different response formats to parse. Moving *all*
provider-specific code into `app/core/llm.py` and giving it two plain
functions - `estimate_simple(description) -> dict` and
`estimate_grounded(description) -> dict` - meant the route handler doesn't
need to know Groq or Gemini exist at all, just "give me an estimate." The
iOS analogue: this is the same shape as defining a protocol and having two
concrete types conform to it, so calling code depends on the protocol, not
either concrete class.

### Caching by content hash: the cheapest possible speedup
`estimate_cache` is one table: a SHA256 hash of the (lowercased, trimmed)
description as the primary key, plus the stored JSON result. Checked before
calling *either* provider. A repeat "a banana" request went from ~1.9s to
~0.24s locally - and more importantly, from one LLM call to zero. This is
about as simple as caching gets (no TTL, no invalidation logic - food facts
for "a banana" don't change), which made it a good first caching pattern to
implement: the interesting design decision wasn't the caching itself, it
was *where* the hash key comes from (normalizing case/whitespace so "A
Banana" and "a banana " share a cache entry) and *who* can access the table
(service-role client only - this table has no per-user owner, and the
endpoint itself has no auth requirement to scope a policy on).

### A graceful-degradation allowlist needs to match reality, not assumptions
The fallback (`estimate_grounded()` catching a failing Gemini call and
retrying via Groq) was written to catch `429` (quota) and `503`
(overloaded) - the two error codes seen live during Level 8's testing.
Testing it for real today (Gemini's quota was still exhausted from earlier
testing, so this was genuinely free to test, not simulated) turned up a
third: after tightening Gemini's client-side timeout from 30s to 10s to
make the fallback feel snappier, some slow-but-not-yet-failed calls started
timing out as `504 DEADLINE_EXCEEDED` instead - a code the allowlist didn't
have, so those specific requests fell all the way through to a bare `502`
instead of gracefully degrading. The bug was caught by directly hammering
`estimate_grounded()` with a batch of distinct real descriptions in a
throwaway script and printing every exception's `type`/`code`, rather than
guessing from a couple of log lines - a `502 Bad Gateway` in the server log
alone didn't say *why* the fallback hadn't triggered. Lesson: an "if this
fails, fall back" allowlist is a hypothesis about what "fails" looks like,
and it should be checked against the actual exceptions a change like a
tightened timeout can introduce, not just the ones seen before that
change.

### The same bug had a second, sneakier form - server error vs. client timeout
Deploying the 504 fix wasn't the end of it. The user's own production
test pass ("oats with milk and honey" 502'd once, then succeeded on a
manual retry) surfaced a *different* uncaught case: a real client-side
timeout, where the request never gets any response from Gemini at all,
raises a plain `httpx.ConnectTimeout`/`ReadTimeout` - not an
`errors.APIError`, because there was no API response to wrap into one.
`isinstance(exc, errors.APIError) and exc.code in (...)` only ever matches
when the *server* returns an error payload; a *client-side give-up* is a
structurally different exception from a different library layer, and the
allowlist check needed a second, separate branch
(`isinstance(exc, httpx.TimeoutException)`) rather than one more code
number. Confirmed by forcing a 1ms timeout in a throwaway script and
checking `type(exc).__mro__` directly rather than guessing from the error
message. The broader lesson: "the server returned an error" and "we gave
up waiting for a response" are two different failure modes even when they
both look like "Gemini is unavailable" from the caller's side, and a
fallback's exception check has to cover both, not just the one that
happened to get tested first.

## LEVEL 10 — Agentic AI, Part 3: A Real Multi-Agent Graph

Phase 3d, same day again: replaced the ad-hoc two-call Gemini flow for
complex meals with an actual LangGraph state machine - four specialized
steps instead of one model doing everything in one or two calls.

### A graph node is just a function that returns a partial state update
The mental model that made LangGraph click: `StateGraph` isn't some exotic
new abstraction, it's a `TypedDict` (the state - `description`,
`parsed_items`, `usda_data`, `estimate`, `validation_errors`, `retries`)
plus plain functions that each take the current state and return a dict of
the keys they want to change. `parse_meal` only returns `{"parsed_items":
[...]}`; it doesn't need to know or care about `usda_data` or `estimate` -
LangGraph merges its return value into the shared state and hands the
result to whatever node is wired up next. That's a genuinely different
shape from a normal Python function chain, where each function has to
either take and return the *entire* growing bundle of data, or you thread
a dozen separate parameters through every call. The graph is what owns the
"what does step 3 need from step 1" bookkeeping instead of the functions
themselves.

### Conditional edges are how "retry the validator's complaint" becomes a graph, not an if-loop
The four nodes (parse → research → estimate → validate) are wired with
plain `add_edge` - a fixed path. The interesting part is `validate`'s
*conditional* edge: a routing function reads the state and returns either
`"retry"` (loop back to `estimate`) or `"done"` (finish). This is a cycle
in the graph, not a fixed pipeline - `estimate` can run 1, 2, or 3 times
depending on whether `validate` keeps rejecting it, and the validation
errors from the failed attempt get folded into the next `estimate` call's
prompt as feedback ("your previous attempt had these problems, fix them").
Verified directly by mocking Groq's responses to return a bad estimate
twice in a row then a good one, and separately by making it fail
persistently to confirm the retry cap (`MAX_VALIDATION_RETRIES = 2`, so 3
total estimate attempts) actually stops the loop instead of running
forever - a graph with a cycle in it needs that cap somewhere, or a single
persistently-wrong model output turns into an unbounded retry storm.

### Specialization made the "no LLM needed" steps obviously cheap
Splitting into four named agents (Parser, Researcher, Estimator,
Validator) made it obvious that two of the four don't need a model call at
all. The Researcher is pure USDA API calls - it doesn't reason about
anything, just fetches data. The Validator is arithmetic (does
protein×4 + carbs×4 + fat×9 roughly equal the reported calories? is
anything negative? is the total in a plausible range for one meal?) - a
rules check, not a judgment call. Naming them as agents up front, before
writing any code, made "which of these actually needs an LLM" a design
question answered before implementation rather than something that
emerged by accident. Net effect: a complex meal now costs 2-3 Groq calls
and some free API lookups, zero Gemini calls in the happy path - a further
reduction from Phase 3b's "Gemini only for complex meals" down to "Gemini
only if the whole agent pipeline fails."

### A three-layer fallback needs each layer tested in isolation, not just the happy path
`estimate_grounded()` now tries the agent pipeline, then the old Gemini
flow, then plain Groq - three layers deep. Verifying only the happy path
(agent pipeline succeeds) would have missed real bugs, so each failure
transition was forced separately with mocks: agent pipeline raises →
does it actually fall to Gemini? Both agent pipeline and Gemini raise →
does it actually fall to Groq, and does the *unexpected* case (not a known
quota/timeout error) get logged with a full traceback rather than
silently swallowed? All three came back correct, but only because each
was checked directly rather than inferred from "well, the try/except looks
right."

### The best-testing-you-can-do bug of the day: your own logging.info() calls being silently dropped
Not a logic bug at all, but the one that would have quietly undermined the
whole point of "add per-node logging for observability" (the plan's
explicit ask for this phase): the FastAPI app never called
`logging.basicConfig()` anywhere. Python's root logger defaults to level
`WARNING` with no handler beyond a silent last-resort one, so every
`logger.info(...)` call across the *entire* app - not just the new agent
pipeline - had been invisible in Render's logs this whole time, while
`.warning()`/`.error()` calls happened to work by accident of already
being at or above the default level. Found by running the pipeline
directly in a throwaway script first (where the script's own
`logging.basicConfig()` was in effect and the logs showed up fine), then
noticing they went silent again once running through the real app. Lesson:
"my code calls logger.info()" is not the same claim as "that log line will
actually appear anywhere" - the two need to be checked separately, and a
missing `basicConfig()` call is an easy thing to never notice until you
specifically need the logs it would have produced.
