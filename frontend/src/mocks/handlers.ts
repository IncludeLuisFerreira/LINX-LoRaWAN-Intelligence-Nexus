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

const tenantAlfaId = crypto.randomUUID();

const mockTenants: MockTenant[] = [
  {
    id: tenantAlfaId,
    name: 'Organização Alfa',
    description: '',
    created_at: now(),
    updated_at: now(),
  },
  {
    id: crypto.randomUUID(),
    name: 'Organização Beta',
    description: '',
    created_at: now(),
    updated_at: now(),
  },
];

const mockAppsByTenant: Record<string, MockApplication[]> = {
  [tenantAlfaId]: [
    {
      id: crypto.randomUUID(),
      name: 'App Sensores',
      description: '',
      created_at: now(),
      updated_at: now(),
    },
  ],
};

interface MockDevice {
  id: string;
  dev_eui: string;
  app_id: string;
  join_eui: string;
  device_profile_id: string;
  created_at: string;
  updated_at: string;
}

const mockDevices: MockDevice[] = [];

const mockDeviceProfiles = [
  { id: crypto.randomUUID(), name: 'Perfil Teste' },
];

function findTenant(tenantId: string): MockTenant | undefined {
  return mockTenants.find((tenant) => tenant.id === tenantId);
}

function findAnyApplication(
  applicationId: string,
): MockApplication | undefined {
  return Object.values(mockAppsByTenant)
    .flat()
    .find((app) => app.id === applicationId);
}

const HEX16 = /^[0-9a-fA-F]{16}$/;
const HEX32 = /^[0-9a-fA-F]{32}$/;

function findApp(
  tenantId: string,
  applicationId: string,
): MockApplication | undefined {
  return (mockAppsByTenant[tenantId] ?? []).find(
    (app) => app.id === applicationId,
  );
}

function tenantNotFound() {
  return HttpResponse.json({ detail: 'Tenant not found!' }, { status: 404 });
}

function applicationNotFound() {
  return HttpResponse.json(
    { detail: 'Application not found!' },
    { status: 404 },
  );
}

function validationError(detail: string) {
  return HttpResponse.json({ detail }, { status: 422 });
}

function createdLocation(request: Request, path: string) {
  return `${new URL(request.url).origin}${path}`;
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
      id: crypto.randomUUID(),
      name: body.name,
      description: body.description ?? '',
      created_at: now(),
      updated_at: now(),
    };
    mockTenants.push(newTenant);
    return HttpResponse.json(newTenant, {
      status: 201,
      headers: {
        Location: createdLocation(request, `/api/v1/tenant/${newTenant.id}`),
      },
    });
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
    if (body.description !== undefined && body.description.length === 0) {
      return validationError('description must not be empty');
    }
    if (body.name !== undefined) tenant.name = body.name;
    if (body.description !== undefined) tenant.description = body.description;
    tenant.updated_at = now();
    return HttpResponse.json(tenant);
  }),

  http.delete('*/api/v1/tenant/:tenant_id', ({ params }) => {
    const id = String(params.tenant_id);
    const index = mockTenants.findIndex((t) => t.id === id);
    if (index === -1) return tenantNotFound();
    mockTenants.splice(index, 1);
    delete mockAppsByTenant[id];
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
      id: crypto.randomUUID(),
      name: body.name,
      description: body.description ?? '',
      created_at: now(),
      updated_at: now(),
    };
    const apps = mockAppsByTenant[tenant.id] ?? [];
    apps.push(newApp);
    mockAppsByTenant[tenant.id] = apps;
    return HttpResponse.json(newApp, {
      status: 201,
      headers: {
        Location: createdLocation(
          request,
          `/api/v1/tenant/${tenant.id}/applications/${newApp.id}`,
        ),
      },
    });
  }),

  http.get(
    '*/api/v1/tenant/:tenant_id/applications/:application_id',
    ({ params }) => {
      const tenant = findTenant(String(params.tenant_id));
      if (!tenant) return tenantNotFound();
      const app = findApp(tenant.id, String(params.application_id));
      if (!app) return applicationNotFound();
      return HttpResponse.json(app);
    },
  ),

  http.patch(
    '*/api/v1/tenant/:tenant_id/applications/:application_id',
    async ({ params, request }) => {
      const tenant = findTenant(String(params.tenant_id));
      if (!tenant) return tenantNotFound();
      const app = findApp(tenant.id, String(params.application_id));
      if (!app) return applicationNotFound();
      const body = (await request.json()) as {
        name?: string;
        description?: string;
      };
      if (body.description !== undefined && body.description.length === 0) {
        return validationError('description must not be empty');
      }
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
      if (index === -1) return applicationNotFound();
      apps.splice(index, 1);
      return new HttpResponse(null, { status: 204 });
    },
  ),

  // --- DEVICE PROFILES ---
  http.get('*/api/v1/device-profile/', ({ request }) => {
    const appId = new URL(request.url).searchParams.get('app_id');
    if (!appId) return validationError('app_id is required');
    return HttpResponse.json(mockDeviceProfiles);
  }),

  // --- DEVICES ---
  http.get('*/api/v1/devices', ({ request }) => {
    const appId = new URL(request.url).searchParams.get('app_id');
    if (!appId) return validationError('app_id is required');
    return HttpResponse.json(
      mockDevices.filter((device) => device.app_id === appId),
    );
  }),

  http.post('*/api/v1/devices', async ({ request }) => {
    const body = (await request.json()) as {
      dev_eui: string;
      app_id: string;
      join_eui: string;
      app_key: string;
      device_profile_id: string;
    };

    if (
      !HEX16.test(body.dev_eui) ||
      !HEX16.test(body.join_eui) ||
      !HEX32.test(body.app_key)
    ) {
      return validationError('invalid device keys');
    }
    if (!findAnyApplication(body.app_id)) return applicationNotFound();
    if (mockDevices.some((device) => device.dev_eui === body.dev_eui)) {
      return HttpResponse.json(
        { detail: 'Device already exists!' },
        { status: 409 },
      );
    }

    const newDevice: MockDevice = {
      id: crypto.randomUUID(),
      dev_eui: body.dev_eui.toLowerCase(),
      app_id: body.app_id,
      join_eui: body.join_eui.toLowerCase(),
      device_profile_id: body.device_profile_id,
      created_at: now(),
      updated_at: now(),
    };
    mockDevices.push(newDevice);
    return HttpResponse.json(newDevice, { status: 201 });
  }),

  http.delete('*/api/v1/devices/:device_id', ({ params }) => {
    const index = mockDevices.findIndex(
      (device) => device.id === String(params.device_id),
    );
    if (index === -1) {
      return HttpResponse.json(
        { detail: 'Device not found!' },
        { status: 404 },
      );
    }
    mockDevices.splice(index, 1);
    return new HttpResponse(null, { status: 204 });
  }),
];
