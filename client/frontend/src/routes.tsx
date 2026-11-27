import { lazy, Suspense } from 'react';
import { Navigate, Routes, Route } from 'react-router-dom';
import { Spinner } from './components/ui/Spinner';
import { AppShell } from './components/layout/AppShell';
import { AuthGuard } from './components/AuthGuard';
import { Can } from './components/Can';

const TenantListPage = lazy(() => import('./pages/tenants/TenantListPage'));
const TenantDetailPage = lazy(() => import('./pages/tenants/TenantDetailPage'));
const ApplicationDetailPage = lazy(
  () => import('./pages/applications/ApplicationDetailPage'),
);
const DeviceListPage = lazy(() => import('./pages/devices/DeviceListPage'));
const Users = lazy(() => import('./pages/users/Users'));
const Rules = lazy(() => import('./pages/rules/Rules'));
const OnboardingWizard = lazy(
  () => import('./pages/onboarding/OnboardingWizard'),
);
const DashboardSelectPage = lazy(
  () => import('./pages/dashboard/DashboardSelectPage'),
);
const Dashboard = lazy(() => import('./pages/dashboard/Dashboard'));
const Login = lazy(() => import('./pages/Login'));
const NotFound = lazy(() => import('./pages/NotFound'));

export function AppRoutes() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center">
          <Spinner size="lg" />
        </div>
      }
    >
      <Routes>
        <Route path="/" element={<Navigate to="/tenants" replace />} />
        <Route path="/login" element={<Login />} />

        <Route
          element={
            <AuthGuard>
              <AppShell />
            </AuthGuard>
          }
        >
          <Route path="/tenants" element={<TenantListPage />} />
          {/*
            Alias aceito como destino pós-login (/orgs) por compatibilidade com o
            critério de aceite; a rota canônica de organizações/tenants é /tenants.
          */}
          <Route path="/orgs" element={<Navigate to="/tenants" replace />} />
          <Route path="/tenants/:tenantId" element={<TenantDetailPage />} />
          <Route
            path="/tenants/:tenantId/users"
            element={
              <Can permission="user:read">
                <Users />
              </Can>
            }
          />
          <Route
            path="/tenants/:tenantId/applications/:appId"
            element={<ApplicationDetailPage />}
          />
          <Route path="/devices" element={<DeviceListPage />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="/dashboard" element={<DashboardSelectPage />} />
          <Route path="/dashboard/:appId" element={<Dashboard />} />
          <Route path="/onboarding" element={<OnboardingWizard />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
