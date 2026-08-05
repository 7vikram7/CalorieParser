-- Small starter catalog so the workout UI has something to search/select.
-- Not exhaustive — extend as needed, or let users add custom exercises.

insert into exercises (name, category, equipment, primary_muscle) values
  ('Barbell Back Squat', 'strength', 'barbell', 'quads'),
  ('Deadlift', 'strength', 'barbell', 'hamstrings'),
  ('Bench Press', 'strength', 'barbell', 'chest'),
  ('Overhead Press', 'strength', 'barbell', 'shoulders'),
  ('Barbell Row', 'strength', 'barbell', 'back'),
  ('Pull-Up', 'strength', 'bodyweight', 'back'),
  ('Push-Up', 'strength', 'bodyweight', 'chest'),
  ('Dumbbell Lunge', 'strength', 'dumbbell', 'quads'),
  ('Plank', 'strength', 'bodyweight', 'core'),
  ('Running', 'cardio', 'none', 'full_body'),
  ('Cycling', 'cardio', 'bike', 'quads'),
  ('Rowing Machine', 'cardio', 'rower', 'full_body');
