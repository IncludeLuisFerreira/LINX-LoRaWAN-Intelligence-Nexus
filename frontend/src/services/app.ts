import { api } from './api';
import type { TenantOutput } from './tenant';

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

export async function loadApplicationsByTenant(
  tenants: TenantOutput[],
  fetchApps: (tenantId: string) => Promise<ApplicationOutput[]> = (tenantId) =>
    applicationService.listByTenant(tenantId),
): Promise<Record<string, ApplicationOutput[]>> {
  const results = await Promise.allSettled(
    tenants.map(async (tenant) => {
      const apps = await fetchApps(tenant.id);
      return [tenant.id, Array.isArray(apps) ? apps : []] as const;
    }),
  );

  return Object.fromEntries(
    results
      .filter((result) => result.status === 'fulfilled')
      .map((result) => result.value),
  );
}
