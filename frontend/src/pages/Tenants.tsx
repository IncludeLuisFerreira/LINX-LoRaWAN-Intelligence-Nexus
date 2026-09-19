import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom'; // 1. Garante que o Link está importado
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
          applicationService.listByTenant(),
        ]);
        setTenants(Array.isArray(tenantsData) ? tenantsData : []);
        setApps(Array.isArray(appsData) ? appsData : []);
      } catch (err) {
        console.error('Erro ao carregar dados:', err);
        setTenants([]);
        setApps([]);
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
      {/* 2. ADICIONA AQUI O CABEÇALHO COM O BOTÃO NOVO TENANT */}
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Tenants</h1>
        <Link
          to="/tenants/new"
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors"
        >
          + Novo Tenant
        </Link>
      </div>

      {/* Listagem abaixo... */}
      <div className="grid gap-6">
        {Array.isArray(tenants) && tenants.length > 0 ? (
          tenants.map((tenant) => {
            const tenantApps = Array.isArray(apps)
              ? apps.filter((app) => app.organizationId === tenant.id)
              : [];

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
                    Nenhuma aplicação cadastrada.
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
          })
        ) : (
          <p className="text-gray-400">Nenhum tenant encontrado.</p>
        )}
      </div>
    </div>
  );
};

export default TenantsPage;
