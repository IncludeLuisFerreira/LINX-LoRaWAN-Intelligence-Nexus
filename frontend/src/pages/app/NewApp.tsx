import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { tenantService } from '../../services/tenant';
import type { TenantOutput } from '../../services/tenant';
import { applicationService } from '../../services/app';
import { getErrorMessage } from '../../services/api';

const newAppSchema = z.object({
  tenantId: z.string().min(1, 'Selecione um tenant obrigatoriamente'),
  name: z
    .string()
    .min(2, 'O nome da aplicação deve ter pelo menos 2 caracteres'),
});

type NewAppFormData = z.infer<typeof newAppSchema>;

const NewApp: React.FC = () => {
  const navigate = useNavigate();
  const [tenants, setTenants] = useState<TenantOutput[]>([]);
  const [loadingTenants, setLoadingTenants] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<NewAppFormData>({
    resolver: zodResolver(newAppSchema),
    defaultValues: {
      tenantId: '',
      name: '',
    },
  });

  const selectedTenantId = watch('tenantId');

  useEffect(() => {
    const fetchTenants = async () => {
      try {
        const data = await tenantService.list();
        setTenants(data || []);
      } catch (err: unknown) {
        setErrorMessage(
          getErrorMessage(err, 'Falha ao carregar a lista de tenants.'),
        );
      } finally {
        setLoadingTenants(false);
      }
    };
    fetchTenants();
  }, []);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (successMessage) {
      timer = setTimeout(() => {
        navigate('/tenants');
      }, 1500);
    }
    return () => clearTimeout(timer);
  }, [successMessage, navigate]);

  const onSubmit = async (data: NewAppFormData) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await applicationService.create(data.tenantId, { name: data.name });
      setSuccessMessage('Aplicação vinculada com sucesso!');
    } catch (err: unknown) {
      setErrorMessage(
        getErrorMessage(err, 'Erro ao vincular aplicação. Verifique os dados.'),
      );
    }
  };

  return (
    <div className="max-w-md mx-auto mt-10 p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">
        Cadastrar Aplicação
      </h2>

      {successMessage && (
        <div className="mb-4 p-3 bg-green-100 text-green-700 rounded-md">
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-md">
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Tenant
          </label>
          <select
            {...register('tenantId')}
            disabled={loadingTenants}
            className="w-full px-3 py-2 text-black bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
          >
            <option value="">
              {loadingTenants ? 'Carregando tenants...' : 'Selecione um tenant'}
            </option>
            {Array.isArray(tenants) &&
              tenants.map((tenant) => (
                <option key={tenant.id} value={tenant.id}>
                  {tenant.name}
                </option>
              ))}
          </select>
          {errors.tenantId && (
            <p className="text-red-500 text-xs mt-1">
              {errors.tenantId.message}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Nome da Aplicação
          </label>
          <input
            type="text"
            {...register('name')}
            placeholder="Ex: Sensor Monitoring"
            className="w-full px-3 py-2 text-black placeholder-gray-400 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {errors.name && (
            <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isSubmitting || !selectedTenantId}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md disabled:opacity-50 transition-colors"
        >
          {isSubmitting ? 'Cadastrando...' : 'Criar Aplicação'}
        </button>
      </form>
    </div>
  );
};

export default NewApp;
