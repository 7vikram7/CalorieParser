"use client";

import { useState, FormEvent } from "react";
import { estimateFood, createCustomFood, createLog, NutritionalEstimate } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"] as const;

export function FoodEstimateForm({ onLogged }: { onLogged: () => void }) {
  const { session } = useAuth();
  const [description, setDescription] = useState("");
  const [estimate, setEstimate] = useState<NutritionalEstimate | null>(null);
  const [mealType, setMealType] = useState<(typeof MEAL_TYPES)[number]>("snack");
  const [quantity, setQuantity] = useState(1);
  const [estimating, setEstimating] = useState(false);
  const [slow, setSlow] = useState(false);
  const [logging, setLogging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleEstimate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setEstimate(null);
    setEstimating(true);
    setSlow(false);
    // The backend runs on Render's free tier, which sleeps after 15 minutes
    // idle and can take 30-50s to wake on a cold request (a few seconds
    // once warm). Rather than let a slow first request look like a silent
    // hang, surface a "waking up" message once it's clearly not just normal
    // latency.
    const slowTimer = setTimeout(() => setSlow(true), 4000);
    try {
      const result = await estimateFood(description);
      setEstimate(result.estimate);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Estimate failed");
    } finally {
      clearTimeout(slowTimer);
      setSlow(false);
      setEstimating(false);
    }
  }

  async function handleLog() {
    if (!estimate || !session) return;
    setError(null);
    setLogging(true);
    try {
      const token = session.access_token;
      const food = await createCustomFood(token, {
        name: estimate.name,
        serving_size_value: estimate.serving_size_value,
        serving_size_unit: estimate.serving_size_unit,
        calories: estimate.calories,
        protein_g: estimate.protein_g,
        carbs_g: estimate.carbs_g,
        fat_g: estimate.fat_g,
      });
      await createLog(token, {
        food_id: food.id,
        log_date: new Date().toISOString().slice(0, 10),
        quantity,
        meal_type: mealType,
      });
      setEstimate(null);
      setDescription("");
      onLogged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logging failed");
    } finally {
      setLogging(false);
    }
  }

  return (
    <div className="rounded-lg border border-black/10 p-4">
      <h2 className="mb-3 font-semibold">Log a meal</h2>
      <form onSubmit={handleEstimate} className="flex gap-2">
        <input
          type="text"
          required
          placeholder="e.g. two scrambled eggs with toast"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          className="flex-1 rounded border border-black/20 px-3 py-2"
        />
        <button
          type="submit"
          disabled={estimating}
          className="rounded bg-black px-4 py-2 text-white disabled:opacity-50"
        >
          {estimating ? "Estimating…" : "Estimate"}
        </button>
      </form>

      {estimating && slow && (
        <p className="mt-3 text-sm text-black/50">
          Waking up the server — this can take up to 30–50s if it has been idle. Hang tight…
        </p>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {estimate && (
        <div className="mt-4 rounded border border-black/10 bg-black/5 p-3">
          <div className="flex items-baseline justify-between">
            <h3 className="font-medium">{estimate.name}</h3>
            <span className="text-sm text-black/60">
              {estimate.serving_size_value} {estimate.serving_size_unit}
            </span>
          </div>
          <p className="mt-1 text-sm">
            {estimate.calories} kcal · P {estimate.protein_g}g · C {estimate.carbs_g}g · F{" "}
            {estimate.fat_g}g
          </p>
          <p className="mt-1 text-xs text-black/50">
            Confidence: {(estimate.confidence * 100).toFixed(0)}%
            {estimate.notes ? ` — ${estimate.notes}` : ""}
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <select
              value={mealType}
              onChange={(e) => setMealType(e.target.value as (typeof MEAL_TYPES)[number])}
              className="rounded border border-black/20 px-2 py-1 text-sm"
            >
              {MEAL_TYPES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
            <input
              type="number"
              min={0.25}
              step={0.25}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="w-20 rounded border border-black/20 px-2 py-1 text-sm"
            />
            <span className="text-sm text-black/50">servings</span>
            <button
              onClick={handleLog}
              disabled={logging}
              className="ml-auto rounded bg-green-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {logging ? "Logging…" : "Log this meal"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
