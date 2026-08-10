"use client";

import { useEffect, useState, FormEvent } from "react";
import { getMyProfile, updateMyProfile, getMyBodyMetrics, upsertMyBodyMetrics, Profile } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";

const ACTIVITY_LEVELS = [
  "sedentary",
  "lightly_active",
  "moderately_active",
  "very_active",
  "extra_active",
] as const;

export function ProfileTab() {
  const { session } = useAuth();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [heightCm, setHeightCm] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [bmr, setBmr] = useState("");
  const [activityLevel, setActivityLevel] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedHint, setSavedHint] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    const token = session.access_token;
    (async () => {
      setLoading(true);
      try {
        const p = await getMyProfile(token);
        setProfile(p);
        setDisplayName(p.display_name ?? "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load profile");
      }
      // A brand-new user has no body_metrics row yet - GET fails until the
      // first PUT creates one via upsert. Treat that as "nothing set" rather
      // than an error.
      try {
        const m = await getMyBodyMetrics(token);
        setHeightCm(m.height_cm?.toString() ?? "");
        setWeightKg(m.weight_kg?.toString() ?? "");
        setBmr(m.bmr?.toString() ?? "");
        setActivityLevel(m.activity_level ?? "");
      } catch {
        // no body metrics yet - leave the form blank
      }
      setLoading(false);
    })();
  }, [session]);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    if (!session) return;
    setSaving(true);
    setError(null);
    setSavedHint(false);
    try {
      const token = session.access_token;
      const p = await updateMyProfile(token, { display_name: displayName || null });
      setProfile(p);
      await upsertMyBodyMetrics(token, {
        height_cm: heightCm ? Number(heightCm) : null,
        weight_kg: weightKg ? Number(weightKg) : null,
        bmr: bmr ? Number(bmr) : null,
        activity_level: activityLevel || null,
      });
      setSavedHint(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-black/50">Loading…</p>;

  return (
    <div className="rounded-lg border border-black/10 p-4">
      <h2 className="mb-3 font-semibold">Profile</h2>
      {profile && (
        <p className="mb-3 text-sm text-black/60">
          {profile.email} {profile.is_coach && <span className="ml-2 text-xs uppercase">Coach</span>}
        </p>
      )}
      <form onSubmit={handleSave} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Display name
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="rounded border border-black/20 px-3 py-2"
          />
        </label>

        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1 text-sm">
            Height (cm)
            <input
              type="number"
              step="0.1"
              value={heightCm}
              onChange={(e) => setHeightCm(e.target.value)}
              className="rounded border border-black/20 px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Weight (kg)
            <input
              type="number"
              step="0.1"
              value={weightKg}
              onChange={(e) => setWeightKg(e.target.value)}
              className="rounded border border-black/20 px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            BMR
            <input
              type="number"
              value={bmr}
              onChange={(e) => setBmr(e.target.value)}
              className="rounded border border-black/20 px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Activity level
            <select
              value={activityLevel}
              onChange={(e) => setActivityLevel(e.target.value)}
              className="rounded border border-black/20 px-3 py-2"
            >
              <option value="">—</option>
              {ACTIVITY_LEVELS.map((a) => (
                <option key={a} value={a}>
                  {a.replace("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {savedHint && <p className="text-sm text-green-700">Saved</p>}

        <button
          type="submit"
          disabled={saving}
          className="self-start rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          {saving ? "Saving…" : "Save"}
        </button>
      </form>
    </div>
  );
}
