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
  if (query.error instanceof ApiError) return <p className="empty">{query.error.message}</p>;
  const data = query.data;
  if (!data) return null;
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Administration</h1>
          <p>{data.note}</p>
        </div>
      </header>
      <article className="card">
        <h2>{data.organization.name}</h2>
        <p>Mode {data.organization.mode}</p>
        <p>Policy {data.organization.policy_version}</p>
      </article>
      <ul>
        {data.principals.map((person) => (
          <li key={person.id}>
            {person.display_name} · {person.email}
          </li>
        ))}
      </ul>
    </>
  );
}
