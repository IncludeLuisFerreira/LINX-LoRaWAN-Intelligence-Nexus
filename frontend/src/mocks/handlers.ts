import { http, HttpResponse } from 'msw';

interface MockTenant {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

interface MockApplication {
  id: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

const now = () => new Date().toISOString();

const mockTenants: MockTenant[] = [
  {
    id: '1',
    name: 'Organização Alfa',
    description: '',
    created_at: now(),
    updated_at: now(),
  },
  {
    id: '2',
    name: 'Organização Beta',
    description: '',
    created_at: now(),
    updated_at: now(),
  },
];

const mockAppsByTenant: Record<string, MockApplication[]> = {
  '1': [
    {
      id: '101',
      name: 'App Sensores',
      description: '',
      created_at: now(),
      updated_at: now(),
    },
  ],
};

function findTenant(tenantId: string): MockTenant | undefined {
  return mockTenants.find((tenant) => tenant.id === tenantId);
}

function tenantNotFound() {
  return HttpResponse.json({ detail: 'Tenant not found!' }, { status: 404 });
}

export const handlers = [
  // --- TENANTS ---
  http.get('*/api/v1/tenant', () => {
    return HttpResponse.json(mockTenants);
  }),

  http.post('*/api/v1/tenant', async ({ request }) => {
    const body = (await request.json()) as {
      name: string;
      description?: string;
    };
    const newTenant: MockTenant = {
      id: String(Date.now()),
      name: body.name,
      description: body.description ?? '',
      created_at: now(),
      updated_at: now(),
    };
    mockTenants.push(newTenant);
    return HttpResponse.json(newTenant, { status: 201 });
  }),

  http.get('*/api/v1/tenant/:tenant_id', ({ params }) => {
    const tenant = findTenant(String(params.tenant_id));
    if (!tenant) return tenantNotFound();
    return HttpResponse.json(tenant);
  }),

  http.patch('*/api/v1/tenant/:tenant_id', async ({ params, request }) => {
    const tenant = findTenant(String(params.tenant_id));
    if (!tenant) return tenantNotFound();

    const body = (await request.json()) as {
      name?: string;
      description?: string;
    };
    if (body.name !== undefined) tenant.name = body.name;
    if (body.description !== undefined) tenant.description = body.description;
    tenant.updated_at = now();
    return HttpResponse.json(tenant);
  }),

  http.delete('*/api/v1/tenant/:tenant_id', ({ params }) => {
    const index = mockTenants.findIndex((t) => t.id === String(params.tenant_id));
    if (index === -1) return tenantNotFound();
    mockTenants.splice(index, 1);
    return new HttpResponse(null, { status: 204 });
  }),

  // --- APPLICATIONS (tenant-scoped) ---
  http.get('*/api/v1/tenant/:tenant_id/applications', ({ params }) => {
    const tenant = findTenant(String(params.tenant_id));
    if (!tenant) return tenantNotFound();
    return HttpResponse.json(mockAppsByTenant[tenant.id] ?? []);
  }),

  http.post('*/api/v1/tenant/:tenant_id/applications', async ({ params, request }) => {
    const tenant = findTenant(String(params.tenant_id));
    if (!tenant) return tenantNotFound();

    const body = (await request.json()) as {
      name: string;
      description?: string;
    };
    const newApp: MockApplication = {
      id: String(Date.now()),
      name: body.name,
      description: body.description ?? '',
      created_at: now(),
      updated_at: now(),
    };
    const apps = mockAppsByTenant[tenant.id] ?? [];
    apps.push(newApp);
    mockAppsByTenant[tenant.id] = apps;
    return HttpResponse.json(newApp, { status: 201 });
  }),

  http.get(
    '*/api/v1/tenant/:tenant_id/applications/:application_id',
    ({ params }) => {
      const tenant = findTenant(String(params.tenant_id));
      if (!tenant) return tenantNotFound();
      const app = (mockAppsByTenant[tenant.id] ?? []).find(
        (a) => a.id === String(params.application_id),
      );
      if (!app) {
        return HttpResponse.json(
          { detail: 'Application not found!' },
          { status: 404 },
        );
      }
      return HttpResponse.json(app);
    },
  ),

  http.patch(
    '*/api/v1/tenant/:tenant_id/applications/:application_id',
    async ({ params, request }) => {
      const tenant = findTenant(String(params.tenant_id));
      if (!tenant) return tenantNotFound();
      const app = (mockAppsByTenant[tenant.id] ?? []).find(
        (a) => a.id === String(params.application_id),
      );
      if (!app) {
        return HttpResponse.json(
          { detail: 'Application not found!' },
          { status: 404 },
        );
      }
      const body = (await request.json()) as {
        name?: string;
        description?: string;
      };
      if (body.name !== undefined) app.name = body.name;
      if (body.description !== undefined) app.description = body.description;
      app.updated_at = now();
      return HttpResponse.json(app);
    },
  ),

  http.delete(
    '*/api/v1/tenant/:tenant_id/applications/:application_id',
    ({ params }) => {
      const tenant = findTenant(String(params.tenant_id));
      if (!tenant) return tenantNotFound();
      const apps = mockAppsByTenant[tenant.id] ?? [];
      const index = apps.findIndex(
        (a) => a.id === String(params.application_id),
      );
      if (index === -1) {
        return HttpResponse.json(
          { detail: 'Application not found!' },
          { status: 404 },
        );
      }
      apps.splice(index, 1);
      return new HttpResponse(null, { status: 204 });
    },
  ),
];
