"use client";

import { useState, FormEvent } from "react";
import { estimateFood, createCustomFood, createLog, NutritionalEstimate } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useSlowLoading, WAKING_UP_MESSAGE } from "@/lib/useSlowLoading";
import { todayStr } from "@/lib/dateUtils";

const MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"] as const;

export function FoodEstimateForm({ onLogged }: { onLogged: () => void }) {
  const { session } = useAuth();
  const [description, setDescription] = useState("");
  const [items, setItems] = useState<NutritionalEstimate[] | null>(null);
  const [mealType, setMealType] = useState<(typeof MEAL_TYPES)[number]>("snack");
  const [estimating, setEstimating] = useState(false);
  const slow = useSlowLoading(estimating);
  const [logging, setLogging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleEstimate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setItems(null);
    setEstimating(true);
    try {
      const result = await estimateFood(description);
      setItems(result.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Estimate failed");
    } finally {
      setEstimating(false);
    }
  }

  function removeItem(index: number) {
    setItems((prev) => (prev ? prev.filter((_, i) => i !== index) : prev));
  }

  // Sum of the items still in the list - a plain client-side total, same
  // principle as the backend's: never independently estimated, always
  // derived from the (possibly user-edited-by-removal) item list.
  // protein_g/carbs_g/fat_g are Decimal on the backend, which serializes
  // over the wire as a JSON string despite the `number` type below (same
  // as FoodLog.quantity elsewhere in this file) - Number(...) is required
  // here or `+` silently does string concatenation instead of summing.
  const total = items?.reduce(
    (acc, item) => ({
      calories: acc.calories + Number(item.calories),
      protein_g: acc.protein_g + Number(item.protein_g),
      carbs_g: acc.carbs_g + Number(item.carbs_g),
      fat_g: acc.fat_g + Number(item.fat_g),
    }),
    { calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0 }
  );

  async function handleLog() {
    if (!items || items.length === 0 || !session) return;
    setError(null);
    setLogging(true);
    try {
      const token = session.access_token;
      // Each item is its own custom_foods + food_logs row, all sharing
      // the same meal_type/date - no cross-request transaction across
      // these N independent two-step creates, so allSettled + a partial-
      // failure message is more honest than pretending it's atomic.
      const results = await Promise.allSettled(
        items.map(async (item) => {
          const food = await createCustomFood(token, {
            name: item.name,
            serving_size_value: item.serving_size_value,
            serving_size_unit: item.serving_size_unit,
            calories: item.calories,
            protein_g: item.protein_g,
            carbs_g: item.carbs_g,
            fat_g: item.fat_g,
          });
          await createLog(token, {
            food_id: food.id,
            log_date: todayStr(),
            quantity: 1,
            meal_type: mealType,
          });
        })
      );
      const failedCount = results.filter((r) => r.status === "rejected").length;
      const succeededCount = results.length - failedCount;
      if (failedCount > 0) {
        setError(
          succeededCount > 0
            ? `${failedCount} of ${items.length} item(s) failed to log. The other ${succeededCount} logged successfully.`
            : "Failed to log any items."
        );
      }
      if (succeededCount > 0) {
        setItems(null);
        setDescription("");
        onLogged();
      }
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

      {estimating && slow && <p className="mt-3 text-sm text-black/50">{WAKING_UP_MESSAGE}</p>}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      {items && items.length > 0 && total && (
        <div className="mt-4 rounded border border-black/10 bg-black/5 p-3">
          <div className="flex items-baseline justify-between">
            <h3 className="font-medium">
              Estimated ({items.length} item{items.length !== 1 ? "s" : ""})
            </h3>
            <span className="text-sm font-medium text-black/60">
              {Math.round(total.calories)} kcal total
            </span>
          </div>

          <ul className="mt-2 flex flex-col gap-2">
            {items.map((item, i) => (
              <li
                key={i}
                className="flex items-start justify-between gap-2 rounded border border-black/10 bg-white px-3 py-2 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-medium">{item.name}</span>
                    <span className="whitespace-nowrap text-black/60">{item.calories} kcal</span>
                  </div>
                  <p className="text-xs text-black/50">
                    {item.serving_size_value} {item.serving_size_unit} · P {item.protein_g}g · C{" "}
                    {item.carbs_g}g · F {item.fat_g}g
                  </p>
                  <p className="text-xs text-black/40">
                    Confidence: {(item.confidence * 100).toFixed(0)}%
                    {item.notes ? ` — ${item.notes}` : ""}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => removeItem(i)}
                  aria-label={`Remove ${item.name}`}
                  className="shrink-0 text-black/40 hover:text-red-600"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>

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
            <button
              onClick={handleLog}
              disabled={logging}
              className="ml-auto rounded bg-green-700 px-3 py-1.5 text-sm text-white disabled:opacity-50"
            >
              {logging ? "Logging…" : `Log ${items.length} item${items.length !== 1 ? "s" : ""}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
