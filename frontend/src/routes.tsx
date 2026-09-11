import { lazy, Suspense } from 'react';
import { Routes, Route } from 'react-router-dom';
import Spinner from './components/Spinner';
import { Layout } from './components/Layout';

const Login = lazy(() => import('./pages/Login'));
const Orgs = lazy(() => import('./pages/Orgs'));
const AppDetail = lazy(() => import('./pages/AppDetail'));
const Devices = lazy(() => import('./pages/Devices'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const NotFound = lazy(() => import('./pages/NotFound'));

export function AppRoutes() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        {/* Rota pública sem Layout */}
        <Route path="/login" element={<Login />} />

        {/* Rotas protegidas envolvidas pelo Layout */}
        <Route element={<Layout />}>
          <Route path="/orgs" element={<Orgs />} />
          <Route path="/apps/:id" element={<AppDetail />} />
          <Route path="/devices" element={<Devices />} />
          <Route path="/dashboard/:appId" element={<Dashboard />} />
        </Route>

        {/* Fallback 404*/}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
