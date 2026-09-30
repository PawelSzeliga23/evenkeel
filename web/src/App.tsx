import { useState } from "react";
import { RouterProvider, createBrowserRouter } from "react-router";
import { StartupSplash } from "./brand/StartupSplash";
import { AppProviders, createQueryClient } from "./providers";
import { appRoutes } from "./routes";

export function App() {
  const [client] = useState(() => createQueryClient());
  const [router] = useState(() => createBrowserRouter(appRoutes));
  return (
    <AppProviders client={client}>
      <StartupSplash />
      <RouterProvider router={router} />
    </AppProviders>
  );
}
