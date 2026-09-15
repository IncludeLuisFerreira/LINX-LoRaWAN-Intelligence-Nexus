import { lazy, Suspense } from 'react';
import { Navigate, Routes, Route } from 'react-router-dom';
import Spinner from './components/Spinner';
import { Layout } from './components/Layout';

// Imports com lazy loading (opcional: você também pode usar lazy para o NewTenant se preferir)
const Login = lazy(() => import('./pages/Login'));
const Tenants = lazy(() => import('./pages/Tenants'));
const NewTenant = lazy(() => import('./pages/tenant/NewTenant'));
const AppDetail = lazy(() => import('./pages/AppDetail'));
const Devices = lazy(() => import('./pages/Devices'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const NotFound = lazy(() => import('./pages/NotFound'));

export function AppRoutes() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        {/* Rotas Públicas */}
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="/login" element={<Login />} />

        {/* Rotas Protegidas / Autenticadas (com Layout da aplicação) */}
        <Route element={<Layout />}>
          <Route path="/tenants" element={<Tenants />} />
          <Route path="/tenants/new" element={<NewTenant />} />{' '}
          {/* Colocado AQUI dentro do Layout */}
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
