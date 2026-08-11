"use client";

import { useEffect, useState, useCallback } from "react";
import { listLogs, listMyFoods, deleteLog, CustomFood, FoodLog } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useSlowLoading, WAKING_UP_MESSAGE } from "@/lib/useSlowLoading";
import { todayStr, addDays } from "@/lib/dateUtils";

function formatHeading(dateStr: string, today: string) {
  if (dateStr === today) return "Today";
  if (dateStr === addDays(today, -1)) return "Yesterday";
  const [year, month, day] = dateStr.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function DailyLog({ refreshKey }: { refreshKey: number }) {
  const { session } = useAuth();
  const today = todayStr();
  const [date, setDate] = useState(today);
  const [logs, setLogs] = useState<FoodLog[]>([]);
  const [foodsById, setFoodsById] = useState<Record<string, CustomFood>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const slow = useSlowLoading(loading);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const token = session.access_token;
      const [dayLogs, foods] = await Promise.all([listLogs(token, date), listMyFoods(token)]);
      setLogs(dayLogs);
      setFoodsById(Object.fromEntries(foods.map((f) => [f.id, f])));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load log");
    } finally {
      setLoading(false);
    }
  }, [session, date]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  useEffect(() => {
    // A freshly logged meal always lands on today (see FoodEstimateForm) -
    // jump the view back there so the user sees it without having to
    // manually navigate back from wherever they were browsing.
    if (refreshKey > 0) setDate(today);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

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
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setDate((d) => addDays(d, -1))}
            aria-label="Previous day"
            className="rounded border border-black/20 px-2 py-1 text-sm"
          >
            ‹
          </button>
          <h2 className="font-semibold">{formatHeading(date, today)}</h2>
          <button
            onClick={() => setDate((d) => addDays(d, 1))}
            aria-label="Next day"
            className="rounded border border-black/20 px-2 py-1 text-sm"
          >
            ›
          </button>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="ml-1 rounded border border-black/20 px-2 py-1 text-xs"
          />
          {date !== today && (
            <button onClick={() => setDate(today)} className="text-xs text-blue-600 underline">
              Today
            </button>
          )}
        </div>
        <span className="text-sm text-black/60">{totalCalories} kcal total</span>
      </div>

      {loading && (
        <p className="text-sm text-black/50">{slow ? WAKING_UP_MESSAGE : "Loading…"}</p>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!loading && logs.length === 0 && (
        <p className="text-sm text-black/50">
          {date === today ? "Nothing logged yet today." : "Nothing logged for this day."}
        </p>
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
