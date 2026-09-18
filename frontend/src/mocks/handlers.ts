import { http, HttpResponse } from 'msw';

const mockTenants = [
  { id: '1', name: 'Organização Alfa', createdAt: new Date().toISOString() },
  { id: '2', name: 'Organização Beta', createdAt: new Date().toISOString() },
];

const mockApps = [
  {
    id: '101',
    name: 'App Sensores',
    organizationId: '1',
    createdAt: new Date().toISOString(),
  },
];

export const handlers = [
  // --- TENANTS ---
  http.get('*/api/v1/tenant', () => {
    return HttpResponse.json(mockTenants);
  }),

  http.post('*/api/v1/tenant', async ({ request }) => {
    const body = (await request.json()) as { name: string };
    const newTenant = {
      id: String(Date.now()),
      name: body.name,
      createdAt: new Date().toISOString(),
    };
    mockTenants.push(newTenant);
    return HttpResponse.json(newTenant, { status: 201 });
  }),

  http.patch('*/api/v1/tenant/:id', async ({ params, request }) => {
    const { id } = params;
    const body = (await request.json()) as { name: string };
    const tenant = mockTenants.find((o) => o.id === id);
    if (tenant && body.name) tenant.name = body.name;
    return HttpResponse.json(tenant ?? null, { status: tenant ? 200 : 404 });
  }),

  http.delete('*/api/v1/tenant/:id', ({ params }) => {
    const { id } = params;
    const index = mockTenants.findIndex((o) => o.id === id);
    if (index !== -1) mockTenants.splice(index, 1);
    return new HttpResponse(null, { status: index !== -1 ? 204 : 404 });
  }),

  // --- APPLICATIONS ---
  http.get('*/api/v1/applications', () => {
    return HttpResponse.json(mockApps);
  }),

  http.post('*/api/v1/applications', async ({ request }) => {
    const body = (await request.json()) as {
      name: string;
      organizationId: string;
      tenantId?: string;
    };

    const orgId = body.tenantId || body.organizationId || '';

    const newApp = {
      id: String(Date.now()),
      name: body.name,
      organizationId: orgId,
      tenantId: orgId,
      createdAt: new Date().toISOString(),
    };
    mockApps.push(newApp);
    return HttpResponse.json(newApp, { status: 201 });
  }),

  http.patch('*/api/v1/applications/:id', async ({ params, request }) => {
    const { id } = params;
    const body = (await request.json()) as { name: string };
    const app = mockApps.find((a) => a.id === id);
    if (app && body.name) app.name = body.name;
    return HttpResponse.json(app);
  }),

  http.delete('*/api/v1/applications/:id', ({ params }) => {
    const { id } = params;
    const index = mockApps.findIndex((a) => a.id === id);
    if (index !== -1) mockApps.splice(index, 1);
    return new HttpResponse(null, { status: 204 });
  }),
];
