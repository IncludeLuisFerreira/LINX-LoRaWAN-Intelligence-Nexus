import { lazy, Suspense } from 'react';
import { Navigate, Routes, Route } from 'react-router-dom';
import { Spinner } from './components/ui/Spinner';
import { AppShell } from './components/layout/AppShell';

const TenantListPage = lazy(() => import('./pages/tenants/TenantListPage'));
const TenantDetailPage = lazy(() => import('./pages/tenants/TenantDetailPage'));
const ApplicationDetailPage = lazy(
  () => import('./pages/applications/ApplicationDetailPage'),
);
const DeviceListPage = lazy(() => import('./pages/devices/DeviceListPage'));
const OnboardingWizard = lazy(
  () => import('./pages/onboarding/OnboardingWizard'),
);
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

        <Route element={<AppShell />}>
          <Route path="/tenants" element={<TenantListPage />} />
          <Route path="/tenants/:tenantId" element={<TenantDetailPage />} />
          <Route
            path="/tenants/:tenantId/applications/:appId"
            element={<ApplicationDetailPage />}
          />
          <Route path="/devices" element={<DeviceListPage />} />
          <Route path="/onboarding" element={<OnboardingWizard />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
