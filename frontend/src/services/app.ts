import { api } from './api';

export interface ApplicationOutput {
  id: string;
  name: string;
  organizationId?: string;
  tenantId?: string;
  createdAt?: string;
}

export interface CreateApplicationInput {
  tenantId: string;
  name: string;
}

export const applicationService = {
  create: async (data: CreateApplicationInput): Promise<ApplicationOutput> => {
    // Envia POST /applications com a prop organizationId que o handlers.ts aguarda
    const response = await api.post<ApplicationOutput>('/applications', {
      name: data.name,
      organizationId: data.tenantId,
    });
    return response.data;
  },

  listByTenant: async (_tenantId?: string): Promise<ApplicationOutput[]> => {
    const response = await api.get<ApplicationOutput[]>('/applications');
    return response.data;
  },
};
