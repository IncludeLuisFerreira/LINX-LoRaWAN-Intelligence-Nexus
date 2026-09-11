import { http, HttpResponse } from 'msw';

const mockOrgs = [
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
  // --- ORGS ---
  http.get('*/api/v1/orgs', () => {
    return HttpResponse.json(mockOrgs);
  }),

  http.post('*/api/v1/orgs', async ({ request }) => {
    const body = (await request.json()) as { name: string };
    const newOrg = {
      id: String(Date.now()),
      name: body.name,
      createdAt: new Date().toISOString(),
    };
    mockOrgs.push(newOrg);
    return HttpResponse.json(newOrg, { status: 201 });
  }),

  http.patch('*/api/v1/orgs/:id', async ({ params, request }) => {
    const { id } = params;
    const body = (await request.json()) as { name: string };
    const org = mockOrgs.find((o) => o.id === id);
    if (org && body.name) org.name = body.name;
    return HttpResponse.json(org);
  }),

  http.delete('*/api/v1/orgs/:id', ({ params }) => {
    const { id } = params;
    const index = mockOrgs.findIndex((o) => o.id === id);
    if (index !== -1) mockOrgs.splice(index, 1);
    return new HttpResponse(null, { status: 204 });
  }),

  // --- APPLICATIONS ---
  http.get('*/api/v1/applications', () => {
    return HttpResponse.json(mockApps);
  }),

  http.post('*/api/v1/applications', async ({ request }) => {
    const body = (await request.json()) as {
      name: string;
      organizationId: string;
    };
    const newApp = {
      id: String(Date.now()),
      name: body.name,
      organizationId: body.organizationId,
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
