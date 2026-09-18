import { lazy, Suspense } from 'react';
import { Navigate, Routes, Route } from 'react-router-dom';
import Spinner from './components/Spinner';
import { Layout } from './components/Layout';

// Imports com lazy loading (opcional: você também pode usar lazy para o NewTenant se preferir)
const Login = lazy(() => import('./pages/Login'));
const Tenants = lazy(() => import('./pages/Tenants'));
const NewTenant = lazy(() => import('./pages/tenants/NewTenant'));
const TenantList = lazy(() => import('./pages/tenants/TenantList'));
const NewApp = lazy(() => import('./pages/app/NewApp'));
const AppDetail = lazy(() => import('./pages/AppDetail'));
const Devices = lazy(() => import('./pages/Devices'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const NotFound = lazy(() => import('./pages/NotFound'));

export function AppRoutes() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />

        <Route element={<Layout />}>
          <Route path="/tenants/list" element={<TenantList />} />
          <Route path="/apps/new" element={<NewApp />} />
          <Route path="/tenants" element={<Tenants />} />
          <Route path="/tenants/new" element={<NewTenant />} />{' '}
          <Route
            path="/tenants/:tenant_id/apps/:app_id"
            element={<AppDetail />}
          />
          <Route path="/tenants/apps/:id/devices" element={<Devices />} />
          <Route path="/tenants/apps/:id/dashboard" element={<Dashboard />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
