"use client";

import { useState } from "react";
import { useAuth } from "@/components/AuthProvider";
import { AuthForm } from "@/components/AuthForm";
import { FoodEstimateForm } from "@/components/FoodEstimateForm";
import { TodayLog } from "@/components/TodayLog";

export default function Home() {
  const { user, loading, signOut } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);

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

      <FoodEstimateForm onLogged={() => setRefreshKey((k) => k + 1)} />
      <TodayLog refreshKey={refreshKey} />
    </div>
  );
}
