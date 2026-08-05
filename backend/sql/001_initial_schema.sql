-- ===========================================================================
-- CalorieParser — initial schema
-- Run against a Supabase Postgres project (SQL editor or `supabase db push`).
-- Depends on Supabase's built-in `auth.users` table for identity/password/JWT.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- profiles
-- One row per auth.users, created automatically on signup via trigger below.
-- Holds identity-ish info that isn't a fitness metric. `is_coach` is a display
-- flag only — real coach authorization always comes from coach_athlete_links.
-- ---------------------------------------------------------------------------
create table profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  display_name text,
  is_coach boolean not null default false,
  created_at timestamptz not null default now()
);

-- `email` is a denormalized copy of auth.users.email — auth.users isn't
-- queryable through PostgREST/RLS, but a coach needs to look an athlete up
-- by email to send an invite. Kept in sync by the two triggers below.
create function handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email) values (new.id, new.email);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure handle_new_user();

create function handle_user_email_update()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  update public.profiles set email = new.email where id = new.id;
  return new;
end;
$$;

create trigger on_auth_user_email_updated
  after update of email on auth.users
  for each row execute procedure handle_user_email_update();

-- ---------------------------------------------------------------------------
-- body_metrics
-- Fitness/body data used for BMR/TDEE calculations. 1:1 with profiles, but
-- kept separate since it changes independently (weigh-ins) and isn't
-- "identity".
-- ---------------------------------------------------------------------------
create table body_metrics (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references profiles (id) on delete cascade,
  height_cm numeric(5, 2),
  weight_kg numeric(5, 2),
  bmr integer,
  activity_level text check (
    activity_level in ('sedentary', 'lightly_active', 'moderately_active', 'very_active', 'extra_active')
  ),
  updated_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- coach_athlete_links
-- The only source of truth for coach access. A link must be 'active' before
-- any RLS policy grants a coach read access to an athlete's data.
-- ---------------------------------------------------------------------------
create table coach_athlete_links (
  id uuid primary key default gen_random_uuid(),
  coach_id uuid not null references profiles (id) on delete cascade,
  athlete_id uuid not null references profiles (id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'active', 'revoked')),
  created_at timestamptz not null default now(),
  responded_at timestamptz,
  constraint coach_athlete_links_no_self_coach check (coach_id <> athlete_id),
  constraint coach_athlete_links_unique_pair unique (coach_id, athlete_id)
);

-- ---------------------------------------------------------------------------
-- custom_foods
-- User-defined foods (MVP: no shared/global food database yet).
-- ---------------------------------------------------------------------------
create table custom_foods (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles (id) on delete cascade,
  name text not null,
  serving_size_value numeric(8, 2) not null,
  serving_size_unit text not null,
  calories integer not null,
  protein_g numeric(6, 2) not null,
  carbs_g numeric(6, 2) not null,
  fat_g numeric(6, 2) not null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- food_logs
-- ---------------------------------------------------------------------------
create table food_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles (id) on delete cascade,
  food_id uuid not null references custom_foods (id) on delete cascade,
  log_date date not null,
  quantity numeric(6, 2) not null,
  meal_type text check (meal_type in ('breakfast', 'lunch', 'dinner', 'snack')),
  created_at timestamptz not null default now()
);

create index food_logs_user_date_idx on food_logs (user_id, log_date);

-- ---------------------------------------------------------------------------
-- exercises
-- Small shared catalog (seeded) + user-added custom exercises.
-- ---------------------------------------------------------------------------
create table exercises (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  category text check (category in ('strength', 'cardio', 'mobility', 'other')),
  equipment text,
  primary_muscle text,
  is_custom boolean not null default false,
  created_by uuid references profiles (id) on delete set null,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- workouts
-- A single logged session (not a template/plan — that's a future feature).
-- ---------------------------------------------------------------------------
create table workouts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles (id) on delete cascade,
  workout_date date not null,
  name text,
  notes text,
  duration_minutes integer,
  created_at timestamptz not null default now()
);

create index workouts_user_date_idx on workouts (user_id, workout_date);

-- ---------------------------------------------------------------------------
-- workout_sets
-- ---------------------------------------------------------------------------
create table workout_sets (
  id uuid primary key default gen_random_uuid(),
  workout_id uuid not null references workouts (id) on delete cascade,
  exercise_id uuid not null references exercises (id) on delete restrict,
  set_number integer not null,
  reps integer,
  weight_kg numeric(6, 2),
  duration_seconds integer,
  distance_m numeric(8, 2),
  rpe numeric(3, 1) check (rpe between 0 and 10),
  notes text,
  constraint workout_sets_unique_set unique (workout_id, exercise_id, set_number)
);

-- ===========================================================================
-- Row Level Security
-- Pattern for every user-owned table: owner has full access; a coach with an
-- 'active' link to that owner gets read-only access. Coaches never get
-- write access to athlete data — logging is always the athlete's own action.
-- ===========================================================================

alter table profiles enable row level security;
alter table body_metrics enable row level security;
alter table coach_athlete_links enable row level security;
alter table custom_foods enable row level security;
alter table food_logs enable row level security;
alter table exercises enable row level security;
alter table workouts enable row level security;
alter table workout_sets enable row level security;

-- profiles: anyone can read a minimal profile (needed to show coach/athlete
-- names to each other); only the owner can update their own row.
create policy "profiles are viewable by any authenticated user"
  on profiles for select
  using (auth.role() = 'authenticated');

create policy "users update own profile"
  on profiles for update
  using (auth.uid() = id);

-- coach_athlete_links: either party in the link can see it. Only the coach
-- can create an invite; only the athlete can flip pending -> active/revoked;
-- either party can revoke an active link.
create policy "parties view own coach links"
  on coach_athlete_links for select
  using (auth.uid() = coach_id or auth.uid() = athlete_id);

create policy "coach creates invite"
  on coach_athlete_links for insert
  with check (auth.uid() = coach_id);

create policy "parties update own coach links"
  on coach_athlete_links for update
  using (auth.uid() = coach_id or auth.uid() = athlete_id);

-- Reusable existence check, referenced by every "coach can read athlete data"
-- policy below.
create function is_active_coach_of(athlete uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from coach_athlete_links
    where coach_athlete_links.athlete_id = athlete
      and coach_athlete_links.coach_id = auth.uid()
      and coach_athlete_links.status = 'active'
  );
$$;

create policy "owner or coach reads body metrics"
  on body_metrics for select
  using (auth.uid() = user_id or is_active_coach_of(user_id));

create policy "owner writes own body metrics"
  on body_metrics for insert with check (auth.uid() = user_id);

create policy "owner updates own body metrics"
  on body_metrics for update using (auth.uid() = user_id);

create policy "owner manages own custom foods"
  on custom_foods for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy "owner or coach reads food logs"
  on food_logs for select
  using (auth.uid() = user_id or is_active_coach_of(user_id));

create policy "owner writes own food logs"
  on food_logs for insert with check (auth.uid() = user_id);

create policy "owner deletes own food logs"
  on food_logs for delete using (auth.uid() = user_id);

create policy "exercise catalog readable by all authenticated users"
  on exercises for select
  using (auth.role() = 'authenticated');

create policy "users add custom exercises"
  on exercises for insert
  with check (auth.uid() = created_by);

create policy "owner or coach reads workouts"
  on workouts for select
  using (auth.uid() = user_id or is_active_coach_of(user_id));

create policy "owner manages own workouts"
  on workouts for insert with check (auth.uid() = user_id);

create policy "owner updates own workouts"
  on workouts for update using (auth.uid() = user_id);

create policy "owner deletes own workouts"
  on workouts for delete using (auth.uid() = user_id);

create policy "owner or coach reads workout sets"
  on workout_sets for select
  using (
    exists (
      select 1 from workouts
      where workouts.id = workout_sets.workout_id
        and (workouts.user_id = auth.uid() or is_active_coach_of(workouts.user_id))
    )
  );

create policy "owner manages own workout sets"
  on workout_sets for insert
  with check (
    exists (
      select 1 from workouts
      where workouts.id = workout_sets.workout_id and workouts.user_id = auth.uid()
    )
  );

create policy "owner updates own workout sets"
  on workout_sets for update
  using (
    exists (
      select 1 from workouts
      where workouts.id = workout_sets.workout_id and workouts.user_id = auth.uid()
    )
  );

create policy "owner deletes own workout sets"
  on workout_sets for delete
  using (
    exists (
      select 1 from workouts
      where workouts.id = workout_sets.workout_id and workouts.user_id = auth.uid()
    )
  );
