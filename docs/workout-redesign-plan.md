# Workout Logging Redesign — Plan

> Status: **Tier 2 + Tier 3 implemented (2026-08-13)**. Tier 1 (auto-import
> from Apple Health / Google Fit) is deferred to the mobile app phase — see
> `docs/roadmap.md` Phase 4.

## Problem

The original workout design required logging every set individually
(exercise, reps, weight, per set). Nobody does this outside of dedicated
powerlifters. Casual users (the large majority) just want something like:
"I did Chest Day, 45 min, hard intensity, and hit a PR on bench at 100kg."

## The 3-tier model

```
TIER 1 — Auto-import (zero effort)                    [deferred — mobile app phase]
  Source: Apple Health / Google Fit / fitness tracker
  Data: activity type, duration, calories, heart rate
  Shows as: workout card ("Strength · 45min · 320 kcal")

TIER 2 — Quick summary (10 seconds)                    [implemented]
  User adds: name ("Chest Day"), intensity toggle (light/moderate/hard)
  Intensity auto-filled from HR zones if tracker provides (N/A until Tier 1 exists)

TIER 3 — Highlights / PRs (30 seconds, optional)        [implemented]
  User adds notable lifts only: "Bench 100kg", "Squat 5x5 @ 80kg"
  Auto-detect PR: if weight exceeds all previous for that exercise, flag it
  Not every warm-up set — just the highlights
```

The detailed set-by-set logging from the original design still exists and
still works — it's now the power-user path, not the only path.

## Schema changes (applied 2026-08-13, see `backend/sql/003_workout_redesign.sql`)

```sql
alter table workouts add column source text not null default 'manual'
  check (source in ('manual', 'apple_health', 'google_fit'));
alter table workouts add column intensity text
  check (intensity in ('light', 'moderate', 'hard'));
alter table workouts add column calories_burned integer;
alter table workouts add column avg_heart_rate integer;

alter table workout_sets add column is_pr boolean not null default false;
```

## PR auto-detection

On `POST /v1/workouts/{workout_id}/sets`, if `weight_kg` is provided, the
backend compares it against every previous set for the same
`(user_id, exercise_id)` pair. If it's a new max, the newly-created set is
flagged `is_pr = true` server-side (not something the client asserts) —
comparison happens under RLS as the calling user, so it only ever looks at
that user's own history.

## UI flow

**Casual user (default):**
```
[Open Workouts tab]
  → "Log a workout" — name (optional), duration, intensity toggle
  → + Add highlight: exercise + weight/reps (as many or few as they want)
  → Highlights that beat a previous max show a PR badge automatically
```

**Power user (opt-in — the original set-by-set flow, unchanged):**
```
[Existing workout] → expand → pick exercise → log full sets with reps/weight/RPE/notes
```

## Explicitly deferred

- Tier 1 (Apple Health / Google Fit auto-import) — needs a mobile app or a
  web Health-data integration; tracked under Phase 4 (Mobile App) in
  `docs/roadmap.md`, not this pass.
- `avg_heart_rate` / `calories_burned` fields exist in the schema now (so
  Tier 1 has somewhere to write to later) but there's no UI to set them yet
  — they're `null` until a Tier 1 data source exists.
