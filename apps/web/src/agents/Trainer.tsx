import { Specialist } from "./shared";

export function Trainer({ principalId }: { principalId: string }) {
  return <Specialist principalId={principalId} />;
}
