import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import Spinner from './components/Spinner';
import { Layout } from './components/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';

const Login = lazy(() => import('./pages/Login'));
const Tenant = lazy(() => import('./pages/Tenant'));
const AppDetail = lazy(() => import('./pages/AppDetail'));
const Devices = lazy(() => import('./pages/Devices'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const NotFound = lazy(() => import('./pages/NotFound'));

export function AppRoutes() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        {/* Rota raiz */}
        <Route path="/" element={<Navigate to="/tenant" replace />} />

        {/* Rota pública */}
        <Route path="/login" element={<Login />} />

        {/* Rotas protegidas */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/tenant" element={<Tenant />} />
            <Route path="/apps/:id" element={<AppDetail />} />
            <Route path="/devices" element={<Devices />} />
            <Route path="/dashboard/:appId" element={<Dashboard />} />
          </Route>
        </Route>

        {/* Fallback 404 */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
