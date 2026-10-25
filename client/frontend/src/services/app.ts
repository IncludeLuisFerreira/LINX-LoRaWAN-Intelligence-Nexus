import { api } from './api';
import type { TenantOutput } from './tenant';

export interface ApplicationOutput {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export const PROVISIONING_STATUS_VALUES = [
  'PENDING',
  'PROVISIONING',
  'RUNNING',
  'ERROR',
] as const;

/** Estados de provisionamento definidos pelo contrato da aplicação. */
export type ProvisioningStatusValue =
  (typeof PROVISIONING_STATUS_VALUES)[number];

export interface CreateApplicationInput {
  name: string;
  description?: string;
}

export interface UpdateApplicationInput {
  name?: string;
  description?: string;
}

/** Opção de aplicação para selects (label "Tenant / App") */
export interface AppOption {
  id: string;
  label: string;
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

  get: async (
    tenantId: string,
    applicationId: string,
  ): Promise<ApplicationOutput> => {
    const response = await api.get<ApplicationOutput>(
      `/tenant/${tenantId}/applications/${applicationId}`,
    );
    return response.data;
  },

  update: async (
    tenantId: string,
    applicationId: string,
    data: UpdateApplicationInput,
  ): Promise<ApplicationOutput> => {
    const response = await api.patch<ApplicationOutput>(
      `/tenant/${tenantId}/applications/${applicationId}`,
      data,
    );
    return response.data;
  },

  remove: async (tenantId: string, applicationId: string): Promise<void> => {
    await api.delete(`/tenant/${tenantId}/applications/${applicationId}`);
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
