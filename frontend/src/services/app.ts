import { api } from './api';

export interface ApplicationOutput {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface CreateApplicationInput {
  name: string;
  description?: string;
}

export const applicationService = {
  create: async (
    tenantId: string,
    data: CreateApplicationInput,
  ): Promise<ApplicationOutput> => {
    const response = await api.post<ApplicationOutput>(
      `/tenant/${tenantId}/applications`,
      data,
    );
    return response.data;
  },

  listByTenant: async (tenantId: string): Promise<ApplicationOutput[]> => {
    const response = await api.get<ApplicationOutput[]>(
      `/tenant/${tenantId}/applications`,
    );
    return response.data;
  },
};
