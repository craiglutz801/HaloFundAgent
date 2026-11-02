import { Specialist } from "./shared";

export function GM({ principalId }: { principalId: string }) {
  return <Specialist principalId={principalId} />;
}
