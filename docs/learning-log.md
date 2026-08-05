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
from fastapi import FastAPI   