import { lazy, Suspense } from 'react';
import { Navigate, Routes, Route } from 'react-router-dom';
import Spinner from './components/Spinner';
import {Layout} from './components/Layout';

const Login = lazy(() => import('./pages/Login'));
const Tenants = lazy(() => import('./pages/Tenants'));
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

        <Route element={<Layout/>}>
          <Route path="/tenants" element={<Tenants />} />
          <Route path="/tenants/:tenant_id/apps/:app_id" element={<AppDetail />} />
          <Route path="/tenants/apps/:id/devices" element={<Devices />} />   
          <Route path="/tenants/apps/:id/dashboard/"element={<Dashboard />} />
          <Route path="*" element={<NotFound />} />
        </Route>
       
      </Routes>
    </Suspense>
  );
}
