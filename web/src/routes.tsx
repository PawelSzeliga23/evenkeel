import { Navigate, type RouteObject } from "react-router";
import { LoginScreen } from "./auth/LoginScreen";
import { RegisterScreen } from "./auth/RegisterScreen";
import { GuestOnly, RequireAuth } from "./auth/RequireAuth";
import { AddScreen } from "./screens/add/AddScreen";
import { BondDetailScreen } from "./screens/bonds/BondDetailScreen";
import { BondForm } from "./screens/add/BondForm";
import { CashForm } from "./screens/add/CashForm";
import { SavingsForm } from "./screens/add/SavingsForm";
import { DashboardScreen } from "./screens/dashboard/DashboardScreen";
import { HistoryScreen } from "./screens/history/HistoryScreen";
import { ExposureScreen } from "./screens/exposure/ExposureScreen";
import { ImportScreen } from "./screens/import/ImportScreen";
import { PositionDetailScreen } from "./screens/positions/PositionDetailScreen";
import { PositionsScreen } from "./screens/positions/PositionsScreen";
import { AccountScreen } from "./screens/settings/AccountScreen";
import { PasswordScreen } from "./screens/settings/PasswordScreen";
import { PriceSourcesScreen } from "./screens/settings/PriceSourcesScreen";
import { SettingsScreen } from "./screens/settings/SettingsScreen";
import { SavingsDetailScreen } from "./screens/savings/SavingsDetailScreen";
import { AppShell } from "./shell/AppShell";

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
          { path: "/pozycje/obligacje/:holdingId", element: <BondDetailScreen /> },
          { path: "/pozycje/oszczednosci/:accountId", element: <SavingsDetailScreen /> },
          { path: "/pozycje/:accountId/:instrumentId", element: <PositionDetailScreen /> },
          { path: "/ekspozycja", element: <ExposureScreen /> },
          { path: "/historia", element: <HistoryScreen /> },
          { path: "/dodaj", element: <AddScreen /> },
          { path: "/dodaj/xtb", element: <ImportScreen /> },
          { path: "/dodaj/obligacja", element: <BondForm /> },
          { path: "/dodaj/operacja", element: <CashForm /> },
          { path: "/dodaj/konto-oszczednosciowe", element: <SavingsForm /> },
          { path: "/ustawienia", element: <SettingsScreen /> },
          { path: "/ustawienia/haslo", element: <PasswordScreen /> },
          { path: "/ustawienia/zrodla-cen", element: <PriceSourcesScreen /> },
          { path: "/ustawienia/konta/:accountId", element: <AccountScreen /> },
          { path: "/wiecej", element: <Navigate to="/ustawienia" replace /> },
          { path: "*", element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
];
