import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { router } from "./routes";
import { SessionProvider, queryClient, useSession } from "./session";

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <RouterGate />
      </SessionProvider>
    </QueryClientProvider>
  );
}

function RouterGate() {
  const session = useSession();
  if (!session.ready) return <div className="skeleton" />;
  return <RouterProvider router={router} />;
}
