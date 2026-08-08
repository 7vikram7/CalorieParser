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

async function apiFetch<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, headers, ...rest } = options;
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });
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
