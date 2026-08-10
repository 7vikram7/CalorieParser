"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabaseClient";
import { onSessionExpired } from "@/lib/authEvents";

type AuthContextValue = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  sessionMessage: string | null;
  clearSessionMessage: () => void;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (email: string, password: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionMessage, setSessionMessage] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  useEffect(() => {
    // lib/api.ts calls this when a 401 survives an explicit refresh attempt
    // - a real expired/invalid session, not just a slow cold start. It has
    // already signed the user out itself; this just surfaces why, instead
    // of the sign-in form silently reappearing with no explanation.
    return onSessionExpired(setSessionMessage);
  }, []);

  useEffect(() => {
    // Fire-and-forget: Render's free tier sleeps after inactivity and can
    // take 30s+ to wake on a cold request. Pinging a real route as soon as
    // the app loads gives the backend a head start before the user gets to
    // the meal-estimate form. Deliberately NOT /health: Render's edge
    // reserves that exact path for its own internal load-balancer probe and
    // never actually routes external requests to the app (confirmed via
    // server logs showing zero external hits on it) — an external ping to
    // /health would 404 at the edge without waking anything. /v1/exercises
    // is unauthenticated, cheap (small seeded table, no AI call), and
    // confirmed to actually reach the app.
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/v1/exercises`).catch(() => {});
  }, []);

  async function signIn(email: string, password: string) {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error?.message ?? null };
  }

  async function signUp(email: string, password: string) {
    const { error } = await supabase.auth.signUp({ email, password });
    return { error: error?.message ?? null };
  }

  async function signOut() {
    await supabase.auth.signOut();
  }

  function clearSessionMessage() {
    setSessionMessage(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user: session?.user ?? null,
        session,
        loading,
        sessionMessage,
        clearSessionMessage,
        signIn,
        signUp,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
