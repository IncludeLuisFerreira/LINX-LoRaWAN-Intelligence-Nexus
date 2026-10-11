import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import DeviceListPage from './DeviceListPage';

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function firstTenantAndApp(): Promise<{
  tenantId: string;
  appId: string;
  appName: string;
}> {
  const tenants = (await (await fetch(`${base}/tenant`)).json()) as {
    id: string;
    name: string;
  }[];
  const tenantId = tenants[0].id;
  const apps = (await (
    await fetch(`${base}/tenant/${tenantId}/applications`)
  ).json()) as { id: string; name: string }[];
  return { tenantId, appId: apps[0].id, appName: apps[0].name };
}

async function createDevice(appId: string, devEui: string) {
  await fetch(`${base}/devices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dev_eui: devEui,
      app_id: appId,
      join_eui: '1122334455667788',
      app_key: '00112233445566778899aabbccddeeff',
    }),
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <DeviceListPage />
    </MemoryRouter>,
  );
}

describe('DeviceListPage', () => {
  it('lists devices with their application and tenant', async () => {
    const { appId, appName } = await firstTenantAndApp();
    await createDevice(appId, 'aabbccddeeff0101');

    renderPage();

    expect(await screen.findByText('aabbccddeeff0101')).toBeInTheDocument();
    expect(screen.getByText(appName)).toBeInTheDocument();
  });

  it('keeps other devices when one application fetch fails', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    await createDevice(appId, 'aabbccddeeff0202');

    const appB = (await (
      await fetch(`${base}/tenant/${tenantId}/applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'App B' }),
      })
    ).json()) as { id: string };

    server.use(
      http.get('*/api/v1/devices', ({ request }) => {
        const requested = new URL(request.url).searchParams.get('app_id');
        if (requested === appB.id) {
          return HttpResponse.json({ detail: 'boom' }, { status: 500 });
        }
        return undefined;
      }),
    );

    renderPage();

    expect(await screen.findByText('aabbccddeeff0202')).toBeInTheDocument();
  });

  it('creates a device through the global modal', async () => {
    const { appId } = await firstTenantAndApp();

    renderPage();
    await screen.findByRole('button', { name: /novo device/i });

    await userEvent.click(
      screen.getAllByRole('button', { name: /novo device/i })[0],
    );
    await userEvent.selectOptions(screen.getByLabelText('Aplicação'), appId);
    await userEvent.type(screen.getByLabelText('DevEUI'), 'AABBCCDDEEFF0303');
    await userEvent.type(
      screen.getByLabelText('JoinEUI'),
      '1122334455667788',
    );
    await userEvent.type(
      screen.getByLabelText('AppKey'),
      '00112233445566778899aabbccddeeff',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Criar' }));

    expect(await screen.findByText('aabbccddeeff0303')).toBeInTheDocument();
  });
});
