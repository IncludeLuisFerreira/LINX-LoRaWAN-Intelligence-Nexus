import { api } from './api';

export interface ApplicationOutput {
  id: string;
  name: string;
  organizationId?: string;
}

export interface CreateApplicationInput {
  organizationId: string;
  name: string;
}

export const applicationService = {
  create: async (data: CreateApplicationInput): Promise<ApplicationOutput> => {
    // Envia POST /applications com a prop organizationId que o handlers.ts aguarda
    const response = await api.post<ApplicationOutput>('/applications', {
      name: data.name,
      organizationId: data.organizationId,
    });
    return response.data;
  },

  listByTenant: async (
    organizationId?: string,
  ): Promise<ApplicationOutput[]> => {
    // Se passar um organizationId, envia como query param para filtrar na API/Mock
    const response = await api.get<ApplicationOutput[]>('/applications', {
      params: organizationId ? { organizationId } : undefined,
    });
    return response.data;
  },
};
