import { AgentWorkspace } from "../pages/AgentWorkspace";

export function Specialist({ principalId }: { principalId: string }) {
  return <AgentWorkspace principalId={principalId} />;
}
