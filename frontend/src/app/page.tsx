"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { AuthForm } from "@/components/AuthForm";
import { FoodEstimateForm } from "@/components/FoodEstimateForm";
import { DailyLog } from "@/components/DailyLog";
import { WorkoutsTab } from "@/components/WorkoutsTab";
import { CoachTab } from "@/components/CoachTab";
import { ProfileTab } from "@/components/ProfileTab";

const TABS = ["Diet", "Workouts", "Coach", "Profile"] as const;
type Tab = (typeof TABS)[number];

export default function Home() {
  const { user, loading, signOut } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);
  const [tab, setTab] = useState<Tab>("Diet");

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
          <DailyLog refreshKey={refreshKey} />
        </>
      )}
      {tab === "Workouts" && <WorkoutsTab />}
      {tab === "Coach" && <CoachTab />}
      {tab === "Profile" && <ProfileTab />}
    </div>
  );
}
