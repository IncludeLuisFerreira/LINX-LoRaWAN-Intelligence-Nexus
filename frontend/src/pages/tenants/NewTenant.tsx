import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { tenantService } from '../../services/tenant';

const tenantSchema = z.object({
  name: z.string().min(2, 'O nome do tenant deve ter pelo menos 2 caracteres'),
});

type TenantFormData = z.infer<typeof tenantSchema>;

const NewTenant: React.FC = () => {
  const navigate = useNavigate();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<TenantFormData>({
    resolver: zodResolver(tenantSchema),
  });

  const onSubmit = async (data: TenantFormData) => {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await tenantService.create(data);
      setSuccessMessage('Tenant criado com sucesso! Redirecionando...');
      setTimeout(() => {
        navigate('/tenants');
      }, 1500);
    } catch (error: any) {
      const apiError =
        error.response?.data?.message ||
        'Erro ao criar tenant. Verifique a conexão com a AWS.';
      setErrorMessage(apiError);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-10 p-6 bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-6 text-gray-800">
        Cadastrar Novo Tenant
      </h2>

      {successMessage && (
        <div className="mb-4 p-3 bg-green-100 text-green-700 rounded-md border border-green-200">
          {successMessage}
        </div>
      )}

      {errorMessage && (
        <div className="mb-4 p-3 bg-red-100 text-red-700 rounded-md border border-red-200">
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Nome do Tenant
          </label>
          <input
            type="text"
            {...register('name')}
            placeholder="Ex: ACME"
            className="w-full px-3 py-2 text-black placeholder:text-gray-400 bg-white border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {errors.name && (
            <p className="text-red-500 text-xs mt-1">{errors.name.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md disabled:opacity-50 transition-colors"
        >
          {isSubmitting ? 'Cadastrando...' : 'Criar Tenant'}
        </button>
      </form>
    </div>
  );
};
export default NewTenant;
