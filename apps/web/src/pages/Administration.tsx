import { useQuery } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";

export function Administration({ principalId }: { principalId: string }) {
  const query = useQuery({
    queryKey: ["admin", principalId],
    queryFn: () =>
      api<{
        organization: { name: string; mode: string; policy_version: string };
        principals: { id: string; display_name: string; email: string }[];
        note: string;
      }>("/api/v1/administration"),
    retry: false,
  });
  if (query.isLoading) return <div className="skeleton" />;
  const denied = query.error instanceof ApiError ? query.error.message : "";
  const data = query.data;
  return (
    <>
      <header className="page-head">
        <div>
          <p className="kicker">System</p>
          <h1>Administration</h1>
          <p>{data?.note ?? "Organization, policy, and the people who can sign in."}</p>
        </div>
      </header>
      {denied && <p className="empty">{denied}</p>}
      {data && (
      <div className="grid two">
        <article className="card">
          <h2 className="panel-title">Organization</h2>
          <p className="org-name">{data.organization.name}</p>
          <p className="meta">
            Mode {data.organization.mode} · policy {data.organization.policy_version}
          </p>
        </article>
        <section className="card">
          <h2 className="panel-title">People</h2>
          <div className="roster">
            {data.principals.map((person) => (
              <div className="roster-row" key={person.id}>
                <strong>{person.display_name}</strong>
                <span className="meta">{person.email}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
      )}
    </>
  );
}
