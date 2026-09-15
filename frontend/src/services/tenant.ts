import { api } from './api';

export interface TenantCreateInput {
  name: string;
}

export interface TenantOutput {
  id: string;
  name: string;
  createdAt?: string;
}

export const tenantService = {
  create: async (data: TenantCreateInput): Promise<TenantOutput> => {
    const response = await api.post<TenantOutput>('/tenant', data);
    return response.data;
  },
  list: async (): Promise<TenantOutput[]> => {
    const response = await api.get<TenantOutput[]>('/tenant');
    return response.data;
  },
};
