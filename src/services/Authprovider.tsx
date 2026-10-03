import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

type AuthState = {
  session: Session | null;
  loading: boolean; // true until the stored session has been read
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(async ({ data }) => {
      // getSession() only reads local storage. Ask the server whether the
      // user still exists, so deleted or banned accounts are signed out.
      if (data.session) {
        const { error } = await supabase.auth.getUser();
        const rejected = error?.status && [401, 403, 404].includes(error.status);
        if (rejected) {
          await supabase.auth.signOut({ scope: "local" });
          setSession(null);
          setLoading(false);
          return;
        }
      }
      setSession(data.session);
      setLoading(false);
    });

    // Fires on sign in, sign out, token refresh and session restore.
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const signOut = async () => {
    await supabase.auth.signOut();
  };

  return (
    <AuthContext.Provider value={{ session, loading, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}