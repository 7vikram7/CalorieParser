-- ---------------------------------------------------------------------------
-- Workout logging redesign — see docs/workout-redesign-plan.md.
--
-- Adds the fields needed for the "quick summary + highlights" flow (Tiers
-- 2-3) alongside the existing set-by-set model (which is unchanged and
-- still fully supported as the power-user path). `source`/`calories_burned`/
-- `avg_heart_rate` also give Tier 1 (Apple Health/Google Fit auto-import,
-- deferred to the mobile app phase) somewhere to write to later.
-- ---------------------------------------------------------------------------

alter table workouts add column source text not null default 'manual'
  check (source in ('manual', 'apple_health', 'google_fit'));
alter table workouts add column intensity text
  check (intensity in ('light', 'moderate', 'hard'));
alter table workouts add column calories_burned integer;
alter table workouts add column avg_heart_rate integer;

-- Set server-side by the backend (compares against the user's previous sets
-- for that exercise on insert) — never client-asserted, so a user can't
-- just claim a PR without actually logging a heavier/better set.
alter table workout_sets add column is_pr boolean not null default false;
