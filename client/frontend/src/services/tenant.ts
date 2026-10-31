import { api } from './api';

export interface TenantOutput {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface CreateTenantInput {
  name: string;
  description?: string;
}

export interface UpdateTenantInput {
  name?: string;
  description?: string;
}

export interface ListTenantsParams {
  skip?: number;
  limit?: number;
}

export const tenantService = {
  create: async (data: CreateTenantInput): Promise<TenantOutput> => {
    const response = await api.post<TenantOutput>('/tenant/', data);
    return response.data;
  },

  list: async (params?: ListTenantsParams): Promise<TenantOutput[]> => {
    const response = await api.get<TenantOutput[]>('/tenant', {
      params,
    });
    return response.data;
  },

  get: async (id: string): Promise<TenantOutput> => {
    const response = await api.get<TenantOutput>(`/tenant/${id}`);
    return response.data;
  },

  update: async (
    id: string,
    data: UpdateTenantInput,
  ): Promise<TenantOutput> => {
    const response = await api.patch<TenantOutput>(`/tenant/${id}`, data);
    return response.data;
  },

  remove: async (id: string): Promise<void> => {
    await api.delete(`/tenant/${id}`);
  },
};
