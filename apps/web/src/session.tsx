import { QueryClient } from "@tanstack/react-query";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, setCsrf } from "./api/client";
import {
  getCsrf,
  getDemoAccess,
  getFixturePrincipals,
  getHealth,
  getMe,
  postDemoAccess,
  postFixtureLogin,
  postLogout,
} from "./api/generated";
import type { Me } from "./api/types";

export type RosterPerson = { id: string; display_name: string; email: string; role: string };

type SessionValue = {
  me: Me | null;
  roster: RosterPerson[];
  ready: boolean;
  needsAccessCode: boolean;
  unlock: (code: string) => Promise<void>;
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
  const [needsAccessCode, setNeedsAccessCode] = useState(false);

  async function loadRoster() {
    setCsrf((await getCsrf()).csrf_token);
    const people = await getFixturePrincipals();
    setRoster(people.principals);
    try {
      setMe(await getMe());
    } catch {
      setMe(null);
    }
  }

  useEffect(() => {
    let active = true;
    async function load() {
      const health = await getHealth();
      if (health.mode === "demo") {
        const gate = await getDemoAccess();
        if (!gate.accepted) {
          if (!active) return;
          setNeedsAccessCode(true);
          setReady(true);
          return;
        }
      }
      if (!active) return;
      setNeedsAccessCode(false);
      await loadRoster();
      if (active) setReady(true);
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
      needsAccessCode,
      unlock: async (code: string) => {
        setCsrf((await getCsrf()).csrf_token);
        try {
          await postDemoAccess({ code });
        } catch (caught) {
          if (caught instanceof ApiError) throw caught;
          throw new ApiError(401, "DEMO_ACCESS_REQUIRED", "That access code is not valid.", {});
        }
        setNeedsAccessCode(false);
        await loadRoster();
      },
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
    [me, roster, ready, needsAccessCode],
  );

  return <SessionContext.Provider value={session}>{children}</SessionContext.Provider>;
}

export function SignIn() {
  const session = useSession();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  return (
    <main className="signin">
      <p className="kicker">Halo Front Office</p>
      <h1>{session.needsAccessCode ? "Demo access" : "Fixture sign-in"}</h1>
      <p className="lede">
        These people are fictional. This copy does not use a commercial identity provider or live capital.
      </p>
      {session.needsAccessCode ? (
        <form
          className="card"
          onSubmit={(event) => {
            event.preventDefault();
            setError("");
            void session.unlock(code).catch((caught: unknown) => {
              setError(caught instanceof ApiError ? caught.message : "That access code is not valid.");
            });
          }}
        >
          <label htmlFor="demo-access-code">Access code</label>
          <input
            id="demo-access-code"
            className="field"
            type="password"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            autoComplete="current-password"
          />
          {error && <p className="error">{error}</p>}
          <button className="button" type="submit">
            Continue
          </button>
        </form>
      ) : (
        <div className="signin-grid">
          {session.roster.map((person) => (
            <button key={person.id} className="card" type="button" onClick={() => void session.signIn(person.id)}>
              <strong>{person.display_name}</strong>
              <div className="meta">{person.role.replaceAll("_", " ")}</div>
            </button>
          ))}
        </div>
      )}
    </main>
  );
}
