import { Navigate, type RouteObject } from "react-router";
import { LoginScreen } from "./auth/LoginScreen";
import { RegisterScreen } from "./auth/RegisterScreen";
import { GuestOnly, RequireAuth } from "./auth/RequireAuth";
import { AddScreen } from "./screens/add/AddScreen";
import { BondForm } from "./screens/add/BondForm";
import { CashForm } from "./screens/add/CashForm";
import { DashboardScreen } from "./screens/dashboard/DashboardScreen";
import { ImportScreen } from "./screens/import/ImportScreen";
import { PositionDetailScreen } from "./screens/positions/PositionDetailScreen";
import { PositionsScreen } from "./screens/positions/PositionsScreen";
import { AppShell } from "./shell/AppShell";
import { MoreScreen } from "./shell/MoreScreen";

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
          { path: "/dodaj", element: <AddScreen /> },
          { path: "/dodaj/xtb", element: <ImportScreen /> },
          { path: "/dodaj/obligacja", element: <BondForm /> },
          { path: "/dodaj/operacja", element: <CashForm /> },
          { path: "/wiecej", element: <MoreScreen /> },
          { path: "*", element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
];
