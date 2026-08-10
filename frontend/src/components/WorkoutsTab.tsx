"use client";

import { useEffect, useState, useCallback, FormEvent } from "react";
import {
  listExercises,
  createExercise,
  createWorkout,
  listMyWorkouts,
  addSet,
  listSets,
  Exercise,
  Workout,
  WorkoutSet,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export function WorkoutsTab() {
  const { session } = useAuth();
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newExerciseName, setNewExerciseName] = useState("");
  const [addingExercise, setAddingExercise] = useState(false);

  const [workoutDate, setWorkoutDate] = useState(new Date().toISOString().slice(0, 10));
  const [workoutName, setWorkoutName] = useState("");
  const [creatingWorkout, setCreatingWorkout] = useState(false);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [setsByWorkout, setSetsByWorkout] = useState<Record<string, WorkoutSet[]>>({});
  const [setExerciseId, setSetExerciseId] = useState("");
  const [setReps, setSetReps] = useState("");
  const [setWeight, setSetWeight] = useState("");
  const [addingSet, setAddingSet] = useState(false);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const token = session.access_token;
      const [ex, wo] = await Promise.all([listExercises(token), listMyWorkouts(token)]);
      setExercises(ex);
      setWorkouts(wo);
      if (ex.length > 0) setSetExerciseId((prev) => prev || ex[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load workouts");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAddExercise(e: FormEvent) {
    e.preventDefault();
    if (!session || !newExerciseName.trim()) return;
    setAddingExercise(true);
    try {
      const ex = await createExercise(session.access_token, { name: newExerciseName });
      setExercises((prev) => [...prev, ex]);
      setNewExerciseName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add exercise");
    } finally {
      setAddingExercise(false);
    }
  }

  async function handleCreateWorkout(e: FormEvent) {
    e.preventDefault();
    if (!session) return;
    setCreatingWorkout(true);
    try {
      const w = await createWorkout(session.access_token, {
        workout_date: workoutDate,
        name: workoutName || null,
      });
      setWorkouts((prev) => [w, ...prev]);
      setWorkoutName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create workout");
    } finally {
      setCreatingWorkout(false);
    }
  }

  async function toggleExpand(workoutId: string) {
    if (expandedId === workoutId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(workoutId);
    if (!setsByWorkout[workoutId] && session) {
      try {
        const sets = await listSets(session.access_token, workoutId);
        setSetsByWorkout((prev) => ({ ...prev, [workoutId]: sets }));
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load sets");
      }
    }
  }

  async function handleAddSet(workoutId: string, e: FormEvent) {
    e.preventDefault();
    if (!session || !setExerciseId) return;
    setAddingSet(true);
    try {
      const existing = setsByWorkout[workoutId] ?? [];
      const set = await addSet(session.access_token, workoutId, {
        exercise_id: setExerciseId,
        set_number: existing.length + 1,
        reps: setReps ? Number(setReps) : null,
        weight_kg: setWeight ? Number(setWeight) : null,
      });
      setSetsByWorkout((prev) => ({ ...prev, [workoutId]: [...existing, set] }));
      setSetReps("");
      setSetWeight("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add set");
    } finally {
      setAddingSet(false);
    }
  }

  if (loading) return <p className="text-sm text-black/50">Loading…</p>;

  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="rounded-lg border border-black/10 p-4">
        <h2 className="mb-3 font-semibold">Exercises</h2>
        <div className="mb-3 flex flex-wrap gap-2">
          {exercises.map((ex) => (
            <span key={ex.id} className="rounded-full bg-black/5 px-3 py-1 text-xs">
              {ex.name}
            </span>
          ))}
        </div>
        <form onSubmit={handleAddExercise} className="flex gap-2">
          <input
            type="text"
            placeholder="Add a custom exercise"
            value={newExerciseName}
            onChange={(e) => setNewExerciseName(e.target.value)}
            className="flex-1 rounded border border-black/20 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={addingExercise}
            className="rounded bg-black px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            Add
          </button>
        </form>
      </div>

      <div className="rounded-lg border border-black/10 p-4">
        <h2 className="mb-3 font-semibold">New workout</h2>
        <form onSubmit={handleCreateWorkout} className="flex flex-wrap gap-2">
          <input
            type="date"
            value={workoutDate}
            onChange={(e) => setWorkoutDate(e.target.value)}
            className="rounded border border-black/20 px-3 py-2 text-sm"
          />
          <input
            type="text"
            placeholder="Name (optional)"
            value={workoutName}
            onChange={(e) => setWorkoutName(e.target.value)}
            className="flex-1 rounded border border-black/20 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={creatingWorkout}
            className="rounded bg-black px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            Create
          </button>
        </form>
      </div>

      <div className="rounded-lg border border-black/10 p-4">
        <h2 className="mb-3 font-semibold">Your workouts</h2>
        {workouts.length === 0 && <p className="text-sm text-black/50">No workouts yet.</p>}
        <ul className="flex flex-col gap-2">
          {workouts.map((w) => (
            <li key={w.id} className="rounded border border-black/10">
              <button
                onClick={() => toggleExpand(w.id)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
              >
                <span>
                  {w.workout_date}
                  {w.name ? ` — ${w.name}` : ""}
                </span>
                <span className="text-black/40">{expandedId === w.id ? "▲" : "▼"}</span>
              </button>

              {expandedId === w.id && (
                <div className="border-t border-black/10 px-3 py-3">
                  <ul className="mb-3 flex flex-col gap-1">
                    {(setsByWorkout[w.id] ?? []).map((s) => {
                      const ex = exercises.find((e) => e.id === s.exercise_id);
                      return (
                        <li key={s.id} className="text-sm text-black/70">
                          Set {s.set_number}: {ex?.name ?? "?"}
                          {s.reps != null ? ` — ${s.reps} reps` : ""}
                          {s.weight_kg != null ? ` @ ${s.weight_kg}kg` : ""}
                        </li>
                      );
                    })}
                    {(setsByWorkout[w.id] ?? []).length === 0 && (
                      <li className="text-sm text-black/40">No sets logged yet.</li>
                    )}
                  </ul>
                  <form
                    onSubmit={(e) => handleAddSet(w.id, e)}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <select
                      value={setExerciseId}
                      onChange={(e) => setSetExerciseId(e.target.value)}
                      className="rounded border border-black/20 px-2 py-1 text-sm"
                    >
                      {exercises.map((ex) => (
                        <option key={ex.id} value={ex.id}>
                          {ex.name}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      placeholder="reps"
                      value={setReps}
                      onChange={(e) => setSetReps(e.target.value)}
                      className="w-20 rounded border border-black/20 px-2 py-1 text-sm"
                    />
                    <input
                      type="number"
                      step="0.5"
                      placeholder="kg"
                      value={setWeight}
                      onChange={(e) => setSetWeight(e.target.value)}
                      className="w-20 rounded border border-black/20 px-2 py-1 text-sm"
                    />
                    <button
                      type="submit"
                      disabled={addingSet || !setExerciseId}
                      className="rounded bg-green-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                    >
                      Add set
                    </button>
                  </form>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
