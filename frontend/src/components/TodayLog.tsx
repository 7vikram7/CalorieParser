"use client";

import { useEffect, useState, useCallback } from "react";
import { listLogs, listMyFoods, deleteLog, CustomFood, FoodLog } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

export function TodayLog({ refreshKey }: { refreshKey: number }) {
  const { session } = useAuth();
  const [logs, setLogs] = useState<FoodLog[]>([]);
  const [foodsById, setFoodsById] = useState<Record<string, CustomFood>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const token = session.access_token;
      const today = new Date().toISOString().slice(0, 10);
      const [todaysLogs, foods] = await Promise.all([
        listLogs(token, today),
        listMyFoods(token),
      ]);
      setLogs(todaysLogs);
      setFoodsById(Object.fromEntries(foods.map((f) => [f.id, f])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load today's log");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  async function handleDelete(logId: string) {
    if (!session) return;
    setDeletingId(logId);
    try {
      await deleteLog(session.access_token, logId);
      setLogs((prev) => prev.filter((l) => l.id !== logId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete log");
    } finally {
      setDeletingId(null);
    }
  }

  const totalCalories = logs.reduce((sum, log) => {
    const food = foodsById[log.food_id];
    return sum + (food ? food.calories * Number(log.quantity) : 0);
  }, 0);

  return (
    <div className="rounded-lg border border-black/10 p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h2 className="font-semibold">Today</h2>
        <span className="text-sm text-black/60">{totalCalories} kcal total</span>
      </div>

      {loading && <p className="text-sm text-black/50">Loading…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && logs.length === 0 && (
        <p className="text-sm text-black/50">Nothing logged yet today.</p>
      )}

      <ul className="flex flex-col gap-2">
        {logs.map((log) => {
          const food = foodsById[log.food_id];
          return (
            <li
              key={log.id}
              className="flex items-baseline justify-between rounded border border-black/10 px-3 py-2 text-sm"
            >
              <span>
                {food?.name ?? "Unknown food"}
                {log.meal_type ? (
                  <span className="ml-2 text-xs text-black/40 uppercase">{log.meal_type}</span>
                ) : null}
              </span>
              <span className="flex items-center gap-2">
                <span className="text-black/60">
                  {food ? Math.round(food.calories * Number(log.quantity)) : "?"} kcal
                </span>
                <button
                  onClick={() => handleDelete(log.id)}
                  disabled={deletingId === log.id}
                  className="text-xs text-red-600 underline disabled:opacity-50"
                >
                  {deletingId === log.id ? "…" : "Delete"}
                </button>
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
