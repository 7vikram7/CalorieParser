-- Phase 3b: cache /v1/foods/estimate responses by a hash of the (lowercased,
-- trimmed) description, so a repeat description costs zero LLM calls. No
-- natural per-user owner - a cached "a banana" answer is the same for every
-- caller - so this is only ever read/written via the service-role client
-- (app/core/llm.py), never through a user-scoped RLS policy. RLS is still
-- enabled with no policies, so even a leaked anon/authenticated token can't
-- read or write it directly.
create table estimate_cache (
  description_hash text primary key,
  description text not null,
  estimate jsonb not null,
  source text not null default 'groq',
  created_at timestamptz not null default now()
);

alter table estimate_cache enable row level security;
