import { Navigate, type RouteObject } from "react-router";
import { LoginScreen } from "./auth/LoginScreen";
import { RegisterScreen } from "./auth/RegisterScreen";
import { GuestOnly, RequireAuth } from "./auth/RequireAuth";
import { DashboardScreen } from "./screens/dashboard/DashboardScreen";
import { PositionDetailScreen } from "./screens/positions/PositionDetailScreen";
import { PositionsScreen } from "./screens/positions/PositionsScreen";
import { AppShell } from "./shell/AppShell";
import { MoreScreen } from "./shell/MoreScreen";

/** Stand-in for the screens built in Tasks 7–9. */
export function Placeholder({ title }: { title: string }) {
  return <h1>{title}</h1>;
}

export const appRoutes: RouteObject[] = [
  {
    element: <GuestOnly />,
    children: [
      { path: "/logowanie", element: <LoginScreen /> },
      { path: "/rejestracja", element: <RegisterScreen /> },
    ],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/", element: <DashboardScreen /> },
          { path: "/pozycje", element: <PositionsScreen /> },
          { path: "/pozycje/:accountId/:instrumentId", element: <PositionDetailScreen /> },
          { path: "/dodaj", element: <Placeholder title="Dodaj" /> },
          { path: "/wiecej", element: <MoreScreen /> },
          { path: "*", element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
];
