"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { AuthForm } from "@/components/AuthForm";
import { FoodEstimateForm } from "@/components/FoodEstimateForm";
import { DailyLog } from "@/components/DailyLog";
import { MacroSummary } from "@/components/MacroSummary";
import { WorkoutsTab } from "@/components/WorkoutsTab";
import { CoachTab } from "@/components/CoachTab";
import { ProfileTab } from "@/components/ProfileTab";
import { getMyProfile } from "@/lib/api";

const TABS = ["Diet", "Workouts", "Coach", "Profile"] as const;
type Tab = (typeof TABS)[number];

export default function Home() {
  const { user, session, loading, signOut } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);
  const [tab, setTab] = useState<Tab>("Diet");
  const [isCoach, setIsCoach] = useState(false);

  useEffect(() => {
    if (!session) return;
    // Fetched once at the page level (not just inside ProfileTab) so the
    // "Coach" badge shows in the header regardless of which tab is open,
    // not only when the user happens to visit the Profile tab.
    getMyProfile(session.access_token)
      .then((p) => setIsCoach(p.is_coach))
      .catch(() => {});
  }, [session]);

  if (loading) {
    return <p className="mt-24 text-center text-sm text-black/50">Loading…</p>;
  }

  if (!user) {
    return <AuthForm />;
  }

  return (
    <div className="mx-auto flex w-full max-w-xl flex-col gap-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">CalorieParser</h1>
        <div className="flex items-center gap-3 text-sm">
          {isCoach && (
            <span className="rounded bg-black px-2 py-0.5 text-xs font-medium uppercase text-white">
              Coach
            </span>
          )}
          <span className="text-black/60">{user.email}</span>
          <button onClick={signOut} className="text-blue-600 underline">
            Sign out
          </button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-black/10">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm ${
              tab === t
                ? "border-b-2 border-black font-medium"
                : "text-black/50 hover:text-black"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Diet" && (
        <>
          <FoodEstimateForm onLogged={() => setRefreshKey((k) => k + 1)} />
          <MacroSummary refreshKey={refreshKey} />
          <DailyLog refreshKey={refreshKey} />
        </>
      )}
      {tab === "Workouts" && <WorkoutsTab />}
      {tab === "Coach" && <CoachTab />}
      {tab === "Profile" && <ProfileTab />}
    </div>
  );
}
