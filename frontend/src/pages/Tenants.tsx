import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { tenantService } from '../services/tenant';
import { applicationService } from '../services/app';
import type { TenantOutput } from '../services/tenant';
import type { ApplicationOutput } from '../services/app';

const TenantsPage: React.FC = () => {
  const [tenants, setTenants] = useState<TenantOutput[]>([]);
  const [apps, setApps] = useState<ApplicationOutput[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [tenantsData, appsData] = await Promise.all([
          tenantService.list(),
          applicationService.listByTenant(''),
        ]);
        setTenants(tenantsData);
        setApps(appsData);
      } catch (err) {
        console.error('Erro ao carregar dados:', err);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  if (loading) {
    return <div className="p-6 text-white">Carregando dados...</div>;
  }

  return (
    <div className="p-6 max-w-5xl text-white">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Página de Tenants</h1>
        <Link
          to="/apps/new"
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm transition-colors"
        >
          + Nova Aplicação
        </Link>
      </div>

      <div className="grid gap-6">
        {tenants.map((tenant) => {
          // Filtra as aplicações pertencentes a este tenant específico
          const tenantApps = apps.filter(
            (app) =>
              app.tenantId === tenant.id || app.organizationId === tenant.id,
          );

          return (
            <div
              key={tenant.id}
              className="bg-gray-800 p-4 rounded-lg border border-gray-700"
            >
              <div className="flex justify-between items-center mb-3 border-b border-gray-700 pb-2">
                <h2 className="text-xl font-semibold text-blue-400">
                  {tenant.name}
                </h2>
                <span className="text-xs text-gray-400 font-mono">
                  ID: {tenant.id}
                </span>
              </div>

              <h3 className="text-sm font-medium text-gray-300 mb-2">
                Aplicações vinculadas:
              </h3>

              {tenantApps.length === 0 ? (
                <p className="text-xs text-gray-500 italic">
                  Nenhuma aplicação cadastrada para este tenant.
                </p>
              ) : (
                <ul className="space-y-1">
                  {tenantApps.map((app) => (
                    <li
                      key={app.id}
                      className="text-sm bg-gray-900 p-2 rounded flex justify-between"
                    >
                      <span>{app.name}</span>
                      <span className="text-xs text-gray-500 font-mono">
                        App ID: {app.id}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default TenantsPage;
