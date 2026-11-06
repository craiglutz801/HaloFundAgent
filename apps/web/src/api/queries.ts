import { useQuery } from "@tanstack/react-query";
import { getCompany, getCompanies, getMe, getOverview, getPacket } from "./generated";

export type SharedQuery = {
  q?: string;
  agent?: string;
  phase?: string;
  outcome?: string;
  scope?: string;
  monitor?: string;
  company?: string;
};

export function filterQuery(search: string): SharedQuery {
  const params = new URLSearchParams(search);
  const query: SharedQuery = {};
  for (const key of ["q", "agent", "phase", "outcome", "scope", "monitor", "company"] as const) {
    const value = params.get(key);
    if (value) query[key] = value;
  }
  return query;
}

export function useMe(enabled: boolean) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => getMe(),
    enabled,
    retry: false,
  });
}

export function useOverview(principalId: string | undefined, search = "") {
  return useQuery({
    queryKey: ["overview", principalId, search],
    queryFn: () => getOverview(filterQuery(search)),
    enabled: Boolean(principalId),
  });
}

export function useCompanies(principalId: string | undefined, search = "") {
  return useQuery({
    queryKey: ["companies", principalId, search],
    queryFn: () => getCompanies(filterQuery(search)),
    enabled: Boolean(principalId),
  });
}

export function useCompany(principalId: string | undefined, companyId: string | undefined, search = "") {
  return useQuery({
    queryKey: ["company", principalId, companyId, search],
    queryFn: () => getCompany(companyId ?? "", filterQuery(search)),
    enabled: Boolean(principalId && companyId),
  });
}

export function usePacket(principalId: string | undefined, packetId: string | undefined) {
  return useQuery({
    queryKey: ["packet", principalId, packetId],
    queryFn: () => getPacket(packetId ?? ""),
    enabled: Boolean(principalId && packetId),
  });
}
