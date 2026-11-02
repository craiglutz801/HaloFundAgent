import { useQuery } from "@tanstack/react-query";
import { getCompany, getCompanies, getMe, getOverview, getPacket } from "./generated";

export function useMe(enabled: boolean) {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => getMe(),
    enabled,
    retry: false,
  });
}

export function useOverview(principalId: string | undefined) {
  return useQuery({
    queryKey: ["overview", principalId],
    queryFn: () => getOverview(),
    enabled: Boolean(principalId),
  });
}

export function useCompanies(principalId: string | undefined) {
  return useQuery({
    queryKey: ["companies", principalId],
    queryFn: () => getCompanies(),
    enabled: Boolean(principalId),
  });
}

export function useCompany(principalId: string | undefined, companyId: string | undefined) {
  return useQuery({
    queryKey: ["company", principalId, companyId],
    queryFn: () => getCompany(companyId ?? ""),
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
