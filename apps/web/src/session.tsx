import { QueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { setCsrf } from "./api/client";
import { getCsrf, getFixturePrincipals, getMe, postFixtureLogin, postLogout } from "./api/generated";
import type { Me } from "./api/types";

export type RosterPerson = { id: string; display_name: string; email: string; role: string };

type SessionValue = {
  me: Me | null;
  roster: RosterPerson[];
  ready: boolean;
  signIn: (principalId: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionValue | null>(null);
export const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: false } },
});

export function useHalo() {
  const value = useContext(SessionContext);
  if (!value?.me) throw new Error("Sign in is required");
  return { ...value, me: value.me, principalId: value.me.principal.id };
}

export function useSession() {
  const value = useContext(SessionContext);
  if (!value) throw new Error("Session missing");
  return value;
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [roster, setRoster] = useState<RosterPerson[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    async function load() {
      setCsrf((await getCsrf()).csrf_token);
      const people = await getFixturePrincipals();
      if (!active) return;
      setRoster(people.principals);
      try {
        const current = await getMe();
        if (active) setMe(current);
      } catch {
        if (active) setMe(null);
      } finally {
        if (active) setReady(true);
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, []);

  const session = useMemo<SessionValue>(
    () => ({
      me,
      roster,
      ready,
      signIn: async (principalId: string) => {
        if (me) await postLogout();
        setCsrf((await getCsrf()).csrf_token);
        const result = await postFixtureLogin({ principal_id: principalId });
        setCsrf(result.csrf_token);
        queryClient.clear();
        setMe(await getMe());
      },
      signOut: async () => {
        await postLogout();
        queryClient.clear();
        setMe(null);
      },
    }),
    [me, roster, ready],
  );

  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

export function SignIn() {
  const session = useSession();
  return (
    <main className="signin">
      <p className="kicker">Halo Front Office</p>
      <h1>Fixture sign-in</h1>
      <p className="lede">These people are fictional. Fixture mode does not use a password or a commercial identity provider.</p>
      <div className="signin-grid">
        {session.roster.map((person) => (
          <button key={person.id} className="card" type="button" onClick={() => void session.signIn(person.id)}>
            <strong>{person.display_name}</strong>
            <div className="meta">{person.role.replaceAll("_", " ")}</div>
          </button>
        ))}
      </div>
    </main>
  );
}
