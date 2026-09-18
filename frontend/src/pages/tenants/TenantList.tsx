import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { tenantService } from '../../services/tenant';
import type { TenantOutput } from '../../services/tenant';

const TenantList: React.FC = () => {
  const [tenants, setTenants] = useState<TenantOutput[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchTenants = async () => {
      try {
        const data = await tenantService.list();
        setTenants(data);
      } catch {
        setError('Não foi possível carregar os tenants.');
      } finally {
        setLoading(false);
      }
    };

    fetchTenants();
  }, []);

  if (loading) {
    return (
      <div className="p-6 text-center text-gray-600">Carregando tenants...</div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto mt-10 p-6 bg-white rounded-lg shadow-md">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Lista de Tenants</h2>
        <Link
          to="/apps/new"
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
        >
          + Nova Aplicação
        </Link>
      </div>

      {error && (
        <div className="p-3 mb-4 bg-red-100 text-red-700 rounded-md">
          {error}
        </div>
      )}

      <div className="border border-gray-200 rounded-md overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-100 border-b border-gray-200">
              <th className="p-3 text-sm font-semibold text-gray-700">ID</th>
              <th className="p-3 text-sm font-semibold text-gray-700">Nome</th>
              <th className="p-3 text-sm font-semibold text-gray-700">
                Criado em
              </th>
            </tr>
          </thead>
          <tbody>
            {tenants.map((tenant) => (
              <tr
                key={tenant.id}
                className="border-b border-gray-100 hover:bg-gray-50 text-black"
              >
                <td className="p-3 text-sm font-mono">{tenant.id}</td>
                <td className="p-3 text-sm font-medium">{tenant.name}</td>
                <td className="p-3 text-sm text-gray-500">
                  {tenant.createdAt
                    ? new Date(tenant.createdAt).toLocaleDateString()
                    : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default TenantList;
