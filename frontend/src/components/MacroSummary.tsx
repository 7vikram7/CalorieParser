"use client";

import { useEffect, useState, useCallback } from "react";
import { getMacroSummary, MacroSummary as MacroSummaryType } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useSlowLoading } from "@/lib/useSlowLoading";
import { LoadingState } from "@/components/Skeleton";

const PERIODS = [
  { value: "week", label: "7 days" },
  { value: "month", label: "30 days" },
] as const;

export function MacroSummary({ refreshKey }: { refreshKey: number }) {
  const { session } = useAuth();
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["value"]>("week");
  const [summary, setSummary] = useState<MacroSummaryType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const slow = useSlowLoading(loading);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const result = await getMacroSummary(session.access_token, period);
      setSummary(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load summary");
    } finally {
      setLoading(false);
    }
  }, [session, period]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  return (
    <div className="rounded-lg border border-black/10 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold">Averages</h2>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p.value}
              onClick={() => setPeriod(p.value)}
              className={`rounded px-2 py-1 text-xs ${
                period === p.value ? "bg-black text-white" : "border border-black/20 text-black/60"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <LoadingState slow={slow} rows={1} />}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {!loading && summary && summary.days_with_logs === 0 && (
        <p className="text-sm text-black/50">No logged days in this period yet.</p>
      )}

      {!loading && summary && summary.days_with_logs > 0 && (
        <>
          <p className="text-sm text-black/50">
            Averaged over {summary.days_with_logs} logged day{summary.days_with_logs !== 1 ? "s" : ""}
          </p>
          <p className="mt-1 text-lg font-semibold">{Math.round(summary.average.calories)} kcal/day</p>
          <p className="text-sm text-black/60">
            P {summary.average.protein_g}g · C {summary.average.carbs_g}g · F {summary.average.fat_g}g
          </p>
        </>
      )}
    </div>
  );
}
