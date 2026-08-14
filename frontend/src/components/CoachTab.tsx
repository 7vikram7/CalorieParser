"use client";

import { useEffect, useState, useCallback, FormEvent } from "react";
import {
  inviteAthlete,
  listPendingInvites,
  respondToInvite,
  listMyAthletes,
  listAthleteLogs,
  listAthleteWorkouts,
  CoachLink,
  FoodLog,
  Workout,
} from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
import { useSlowLoading } from "@/lib/useSlowLoading";
import { LoadingState } from "@/components/Skeleton";

export function CoachTab() {
  const { session } = useAuth();
  const [pending, setPending] = useState<CoachLink[]>([]);
  const [athletes, setAthletes] = useState<CoachLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const slow = useSlowLoading(loading);

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteSentTo, setInviteSentTo] = useState<string | null>(null);

  const [respondingId, setRespondingId] = useState<string | null>(null);

  const [expandedAthleteId, setExpandedAthleteId] = useState<string | null>(null);
  const [athleteLogs, setAthleteLogs] = useState<FoodLog[]>([]);
  const [athleteWorkouts, setAthleteWorkouts] = useState<Workout[]>([]);
  const [loadingAthleteData, setLoadingAthleteData] = useState(false);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    setError(null);
    try {
      const token = session.access_token;
      const [p, a] = await Promise.all([listPendingInvites(token), listMyAthletes(token)]);
      setPending(p);
      setAthletes(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load coaching data");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleInvite(e: FormEvent) {
    e.preventDefault();
    if (!session || !inviteEmail.trim()) return;
    setInviting(true);
    setInviteSentTo(null);
    setError(null);
    const sentTo = inviteEmail.trim();
    try {
      await inviteAthlete(session.access_token, sentTo);
      setInviteEmail("");
      setInviteSentTo(sentTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send invite");
    } finally {
      setInviting(false);
    }
  }

  async function handleRespond(linkId: string, status: "active" | "revoked") {
    if (!session) return;
    setRespondingId(linkId);
    try {
      await respondToInvite(session.access_token, linkId, status);
      setPending((prev) => prev.filter((l) => l.id !== linkId));
      if (status === "active") load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to respond to invite");
    } finally {
      setRespondingId(null);
    }
  }

  async function toggleAthlete(link: CoachLink) {
    if (expandedAthleteId === link.athlete_id) {
      setExpandedAthleteId(null);
      return;
    }
    setExpandedAthleteId(link.athlete_id);
    if (!session) return;
    setLoadingAthleteData(true);
    try {
      const token = session.access_token;
      const [logs, workouts] = await Promise.all([
        listAthleteLogs(token, link.athlete_id),
        listAthleteWorkouts(token, link.athlete_id),
      ]);
      setAthleteLogs(logs);
      setAthleteWorkouts(workouts);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load athlete data");
    } finally {
      setLoadingAthleteData(false);
    }
  }

  if (loading) {
    return <LoadingState slow={slow} />;
  }

  return (
    <div className="flex flex-col gap-4">
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="rounded-lg border border-black/10 p-4">
        <h2 className="mb-3 font-semibold">Invite an athlete</h2>
        <form onSubmit={handleInvite} className="flex gap-2">
          <input
            type="email"
            placeholder="athlete@example.com"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            className="flex-1 rounded border border-black/20 px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={inviting}
            className="rounded bg-black px-3 py-2 text-sm text-white disabled:opacity-50"
          >
            {inviting ? "Sending…" : "Invite"}
          </button>
        </form>
        {inviteSentTo && (
          <p className="mt-2 text-sm text-green-700">Invite sent to {inviteSentTo}.</p>
        )}
      </div>

      <div className="rounded-lg border border-black/10 p-4">
        <h2 className="mb-3 font-semibold">Invites waiting on you</h2>
        {pending.length === 0 && (
          <p className="text-sm text-black/50">No pending invites from a coach.</p>
        )}
        <ul className="flex flex-col gap-2">
          {pending.map((link) => (
            <li
              key={link.id}
              className="flex items-center justify-between rounded border border-black/10 px-3 py-2 text-sm"
            >
              <span>Coach invite: {link.coach_name ?? link.coach_email ?? link.coach_id}</span>
              <span className="flex gap-2">
                <button
                  onClick={() => handleRespond(link.id, "active")}
                  disabled={respondingId === link.id}
                  className="rounded bg-green-700 px-2 py-1 text-xs text-white disabled:opacity-50"
                >
                  Accept
                </button>
                <button
                  onClick={() => handleRespond(link.id, "revoked")}
                  disabled={respondingId === link.id}
                  className="rounded border border-black/20 px-2 py-1 text-xs disabled:opacity-50"
                >
                  Decline
                </button>
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-lg border border-black/10 p-4">
        <h2 className="mb-3 font-semibold">Your athletes</h2>
        {athletes.length === 0 && (
          <p className="text-sm text-black/50">No active athletes yet.</p>
        )}
        <ul className="flex flex-col gap-2">
          {athletes.map((link) => (
            <li key={link.id} className="rounded border border-black/10">
              <button
                onClick={() => toggleAthlete(link)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
              >
                <span>{link.athlete_name ?? link.athlete_email ?? link.athlete_id}</span>
                <span className="text-black/40">
                  {expandedAthleteId === link.athlete_id ? "▲" : "▼"}
                </span>
              </button>
              {expandedAthleteId === link.athlete_id && (
                <div className="border-t border-black/10 px-3 py-3 text-sm">
                  {loadingAthleteData ? (
                    <p className="text-black/50">Loading…</p>
                  ) : (
                    <>
                      <p className="mb-1 font-medium">Recent logs</p>
                      {athleteLogs.length === 0 ? (
                        <p className="mb-2 text-black/40">No logs yet.</p>
                      ) : (
                        <ul className="mb-2 flex flex-col gap-1">
                          {athleteLogs.map((l) => (
                            <li key={l.id} className="text-black/70">
                              {l.log_date} — {l.meal_type ?? "meal"} ({l.quantity}x)
                            </li>
                          ))}
                        </ul>
                      )}
                      <p className="mb-1 font-medium">Recent workouts</p>
                      {athleteWorkouts.length === 0 ? (
                        <p className="text-black/40">No workouts yet.</p>
                      ) : (
                        <ul className="flex flex-col gap-1">
                          {athleteWorkouts.map((w) => (
                            <li key={w.id} className="text-black/70">
                              {w.workout_date}
                              {w.name ? ` — ${w.name}` : ""}
                            </li>
                          ))}
                        </ul>
                      )}
                    </>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
