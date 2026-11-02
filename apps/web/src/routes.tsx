import { createBrowserRouter, Navigate, useParams } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { SignIn, useHalo, useSession } from "./session";
import { Ainge } from "./agents/Ainge";
import { GM } from "./agents/GM";
import { Mutombo } from "./agents/Mutombo";
import { Scout } from "./agents/Scout";
import { Scorekeeper } from "./agents/Scorekeeper";
import { Sloan } from "./agents/Sloan";
import { Stockton } from "./agents/Stockton";
import { Trainer } from "./agents/Trainer";
import { Xavier } from "./agents/Xavier";
import { Administration } from "./pages/Administration";
import { AgentDirectory } from "./pages/AgentDirectory";
import { AgentWorkspace } from "./pages/AgentWorkspace";
import { CompanyFlow } from "./pages/CompanyFlow";
import { CompanyWorkspace } from "./pages/CompanyWorkspace";
import { Overview } from "./pages/Overview";
import { PacketReview } from "./pages/PacketReview";
import { Portfolio } from "./pages/Portfolio";
import { ReviewQueue } from "./pages/ReviewQueue";
import { RunPage } from "./pages/RunPage";
import { ValueLedger } from "./pages/ValueLedger";

const AGENTS = {
  gm: GM,
  scout: Scout,
  ainge: Ainge,
  xavier: Xavier,
  mutombo: Mutombo,
  stockton: Stockton,
  sloan: Sloan,
  trainer: Trainer,
  scorekeeper: Scorekeeper,
};

function Gate() {
  const session = useSession();
  if (!session.me) return <SignIn />;
  return (
    <AppShell
      me={session.me}
      roster={session.roster}
      onSwitch={(principalId) => {
        void session.signIn(principalId);
      }}
    />
  );
}

function Home() {
  const { principalId } = useHalo();
  return <Overview principalId={principalId} />;
}
function Companies() {
  const { principalId } = useHalo();
  return <CompanyFlow principalId={principalId} />;
}
function Company() {
  const { principalId, me } = useHalo();
  return <CompanyWorkspace principalId={principalId} me={me} />;
}
function Agents() {
  const { principalId } = useHalo();
  return <AgentDirectory principalId={principalId} />;
}
function AgentPage() {
  const { principalId } = useHalo();
  const { agentId = "" } = useParams();
  const Page = AGENTS[agentId as keyof typeof AGENTS];
  if (Page) return <Page principalId={principalId} />;
  return <AgentWorkspace principalId={principalId} />;
}
function Run() {
  const { principalId } = useHalo();
  return <RunPage principalId={principalId} />;
}
function Review() {
  const { principalId } = useHalo();
  return <ReviewQueue principalId={principalId} />;
}
function Packet() {
  const { principalId } = useHalo();
  return <PacketReview principalId={principalId} />;
}
function PortfolioPage() {
  const { principalId } = useHalo();
  return <Portfolio principalId={principalId} />;
}
function Value() {
  const { principalId } = useHalo();
  return <ValueLedger principalId={principalId} />;
}
function Admin() {
  const { principalId } = useHalo();
  return <Administration principalId={principalId} />;
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Gate />,
    children: [
      { index: true, element: <Home /> },
      { path: "companies", element: <Companies /> },
      { path: "companies/:companyId", element: <Company /> },
      { path: "companies/:companyId/cases/:caseId", element: <Company /> },
      { path: "companies/:companyId/agents/:agentId", element: <AgentPage /> },
      { path: "companies/:companyId/agents/:agentId/runs/:runId", element: <Run /> },
      { path: "agents", element: <Agents /> },
      { path: "agents/:agentId", element: <AgentPage /> },
      { path: "review", element: <Review /> },
      { path: "review/packets/:packetId", element: <Packet /> },
      { path: "portfolio", element: <PortfolioPage /> },
      { path: "value", element: <Value /> },
      { path: "administration", element: <Admin /> },
      { path: "*", element: <Navigate to="/" replace /> },
    ],
  },
]);
