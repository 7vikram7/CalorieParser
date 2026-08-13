import { supabase } from "./supabaseClient";
import { emitSessionExpired } from "./authEvents";

const API_URL = process.env.NEXT_PUBLIC_API_URL!;

export type NutritionalEstimate = {
  name: string;
  serving_size_value: number;
  serving_size_unit: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  confidence: number;
  notes: string | null;
};

export type FoodEstimateResponse = {
  description: string;
  estimate: NutritionalEstimate;
};

export type CustomFood = {
  id: string;
  user_id: string;
  created_at: string;
  name: string;
  serving_size_value: number;
  serving_size_unit: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
};

export type FoodLog = {
  id: string;
  user_id: string;
  created_at: string;
  food_id: string;
  log_date: string;
  quantity: number;
  meal_type: string | null;
};

export type Profile = {
  id: string;
  email: string;
  is_coach: boolean;
  created_at: string;
  display_name: string | null;
};

export type BodyMetrics = {
  id: string;
  user_id: string;
  updated_at: string;
  height_cm: number | null;
  weight_kg: number | null;
  bmr: number | null;
  activity_level: string | null;
};

export type Exercise = {
  id: string;
  is_custom: boolean;
  created_by: string | null;
  created_at: string;
  name: string;
  category: string | null;
  equipment: string | null;
  primary_muscle: string | null;
};

export type WorkoutSource = "manual" | "apple_health" | "google_fit";
export type WorkoutIntensity = "light" | "moderate" | "hard";

export type Workout = {
  id: string;
  user_id: string;
  created_at: string;
  workout_date: string;
  name: string | null;
  notes: string | null;
  duration_minutes: number | null;
  source: WorkoutSource;
  intensity: WorkoutIntensity | null;
  calories_burned: number | null;
  avg_heart_rate: number | null;
};

export type WorkoutSet = {
  id: string;
  workout_id: string;
  exercise_id: string;
  set_number: number;
  reps: number | null;
  weight_kg: number | null;
  duration_seconds: number | null;
  distance_m: number | null;
  rpe: number | null;
  notes: string | null;
  is_pr: boolean;
};

export type CoachLinkStatus = "pending" | "active" | "revoked";

export type CoachLink = {
  id: string;
  coach_id: string;
  athlete_id: string;
  status: CoachLinkStatus;
  created_at: string;
  responded_at: string | null;
};

function doFetch(path: string, token: string | undefined, init: RequestInit) {
  return fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
}

async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, headers, ...rest } = options;
  let res = await doFetch(path, token, { ...rest, headers });

  if (res.status === 401 && token) {
    // Supabase auto-refreshes access tokens in the background, but that can
    // lag behind reality - e.g. a backgrounded browser tab throttles timers,
    // so the in-memory token can be stale by the time a request actually
    // fires. Try one explicit refresh + retry before treating this as a
    // real session expiry.
    const { data, error } = await supabase.auth.refreshSession();
    if (!error && data.session) {
      res = await doFetch(path, data.session.access_token, { ...rest, headers });
    }
    if (res.status === 401) {
      await supabase.auth.signOut();
      emitSessionExpired("Your session expired — please sign in again.");
    }
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function estimateFood(description: string) {
  return apiFetch<FoodEstimateResponse>("/v1/foods/estimate", {
    method: "POST",
    body: JSON.stringify({ description }),
  });
}

export function createCustomFood(
  token: string,
  payload: Omit<CustomFood, "id" | "user_id" | "created_at">
) {
  return apiFetch<CustomFood>("/v1/foods", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function createLog(
  token: string,
  payload: { food_id: string; log_date: string; quantity: number; meal_type?: string | null }
) {
  return apiFetch<FoodLog>("/v1/logs", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function listLogs(token: string, logDate?: string) {
  const qs = logDate ? `?log_date=${logDate}` : "";
  return apiFetch<FoodLog[]>(`/v1/logs${qs}`, { token });
}

export function listMyFoods(token: string) {
  return apiFetch<CustomFood[]>("/v1/foods", { token });
}

export function deleteLog(token: string, logId: string) {
  return apiFetch<void>(`/v1/logs/${logId}`, { method: "DELETE", token });
}

export function listAthleteLogs(token: string, athleteId: string, logDate?: string) {
  const qs = logDate ? `?log_date=${logDate}` : "";
  return apiFetch<FoodLog[]>(`/v1/logs/athlete/${athleteId}${qs}`, { token });
}

// ---- Profile & body metrics ----

export function getMyProfile(token: string) {
  return apiFetch<Profile>("/v1/profiles/me", { token });
}

export function updateMyProfile(token: string, payload: { display_name?: string | null }) {
  return apiFetch<Profile>("/v1/profiles/me", {
    method: "PATCH",
    token,
    body: JSON.stringify(payload),
  });
}

export function getMyBodyMetrics(token: string) {
  return apiFetch<BodyMetrics>("/v1/profiles/me/body-metrics", { token });
}

export function upsertMyBodyMetrics(
  token: string,
  payload: Partial<Omit<BodyMetrics, "id" | "user_id" | "updated_at">>
) {
  return apiFetch<BodyMetrics>("/v1/profiles/me/body-metrics", {
    method: "PUT",
    token,
    body: JSON.stringify(payload),
  });
}

// ---- Workouts & exercises ----

export function listExercises(token: string) {
  return apiFetch<Exercise[]>("/v1/exercises", { token });
}

export function createExercise(
  token: string,
  payload: { name: string; category?: string | null; equipment?: string | null; primary_muscle?: string | null }
) {
  return apiFetch<Exercise>("/v1/exercises", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function createWorkout(
  token: string,
  payload: {
    workout_date: string;
    name?: string | null;
    notes?: string | null;
    duration_minutes?: number | null;
    intensity?: WorkoutIntensity | null;
  }
) {
  return apiFetch<Workout>("/v1/workouts", {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function listMyWorkouts(token: string, workoutDate?: string) {
  const qs = workoutDate ? `?workout_date=${workoutDate}` : "";
  return apiFetch<Workout[]>(`/v1/workouts${qs}`, { token });
}

export function listAthleteWorkouts(token: string, athleteId: string) {
  return apiFetch<Workout[]>(`/v1/workouts/athlete/${athleteId}`, { token });
}

export function addSet(
  token: string,
  workoutId: string,
  payload: {
    exercise_id: string;
    set_number: number;
    reps?: number | null;
    weight_kg?: number | null;
    duration_seconds?: number | null;
    distance_m?: number | null;
    rpe?: number | null;
    notes?: string | null;
  }
) {
  return apiFetch<WorkoutSet>(`/v1/workouts/${workoutId}/sets`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function listSets(token: string, workoutId: string) {
  return apiFetch<WorkoutSet[]>(`/v1/workouts/${workoutId}/sets`, { token });
}

// ---- Coaching ----

export function inviteAthlete(token: string, athleteEmail: string) {
  return apiFetch<CoachLink>("/v1/coaches/invite", {
    method: "POST",
    token,
    body: JSON.stringify({ athlete_email: athleteEmail }),
  });
}

export function listPendingInvites(token: string) {
  return apiFetch<CoachLink[]>("/v1/coaches/invites/pending", { token });
}

export function respondToInvite(token: string, linkId: string, status: "active" | "revoked") {
  return apiFetch<CoachLink>(`/v1/coaches/links/${linkId}`, {
    method: "PATCH",
    token,
    body: JSON.stringify({ status }),
  });
}

export function listMyAthletes(token: string) {
  return apiFetch<CoachLink[]>("/v1/coaches/athletes", { token });
}
