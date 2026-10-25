import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import ApplicationDetailPage from './ApplicationDetailPage';

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

async function createDevice(appId: string, devEui: string, nickname?: string) {
  await fetch(`${base}/devices`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dev_eui: devEui,
      app_id: appId,
      join_eui: '1122334455667788',
      app_key: '00112233445566778899aabbccddeeff',
      device_profile_id: 'profile-test',
      nickname,
    }),
  });
}

function renderDetail(tenantId: string, appId: string) {
  return render(
    <MemoryRouter
      initialEntries={[`/tenants/${tenantId}/applications/${appId}`]}
    >
      <Routes>
        <Route
          path="/tenants/:tenantId/applications/:appId"
          element={<ApplicationDetailPage />}
        />
        <Route path="/onboarding" element={<div>wizard-page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ApplicationDetailPage', () => {
  it('renders the app and shows an empty device state', async () => {
    const { tenantId, appId, appName } = await firstTenantAndApp();

    renderDetail(tenantId, appId);

    expect(
      await screen.findByRole('heading', { name: appName }),
    ).toBeInTheDocument();
    expect(screen.getByText('Nenhum device')).toBeInTheDocument();
  });

  it('navigates to the onboarding wizard scoped to the app', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    renderDetail(tenantId, appId);
    await screen.findByText('Nenhum device');

    await userEvent.click(
      screen.getAllByRole('button', { name: /novo device/i })[0],
    );

    expect(await screen.findByText('wizard-page')).toBeInTheDocument();
  });

  it('shows the nickname and edits it from the device table', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    await fetch(`${base}/devices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dev_eui: 'aabbccddeeff0707',
        app_id: appId,
        join_eui: '1122334455667788',
        app_key: '00112233445566778899aabbccddeeff',
        device_profile_id: 'profile-test',
        nickname: 'Sensor A',
      }),
    });

    renderDetail(tenantId, appId);
    await screen.findByText('aabbccddeeff0707');
    expect(screen.getByText('Sensor A')).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: 'Editar nickname aabbccddeeff0707' }),
    );
    const input = await screen.findByLabelText('Nickname');
    await userEvent.clear(input);
    await userEvent.type(input, 'Sensor B');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('Sensor B')).toBeInTheDocument();
  });

  it('shows online status and the last telemetry for a recent device', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    const devEui = 'aabbccddeeff1404';
    await createDevice(appId, devEui, 'Sensor Recente');
    const time = new Date(Date.now() - 10_000).toISOString();

    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        const requested = new URL(request.url).searchParams.get('dev_eui');
        return HttpResponse.json({
          items:
            requested === devEui
              ? [
                  {
                    time,
                    dev_eui: devEui,
                    payload: { temperature: 24.5 },
                    rssi: -70,
                    snr: 7,
                    app_id: appId,
                    event_type: 'up',
                  },
                ]
              : [],
          next_cursor: null,
        });
      }),
    );

    renderDetail(tenantId, appId);
    const row = (await screen.findByText(devEui)).closest('tr');
    expect(row).not.toBeNull();

    expect(
      await within(row as HTMLElement).findByText('Online'),
    ).toBeInTheDocument();
    expect(
      within(row as HTMLElement).getByText(/temperature: 24\.5/),
    ).toBeInTheDocument();
  });

  it('shows offline status when telemetry is older than 60 seconds', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    const devEui = 'aabbccddeeff1505';
    await createDevice(appId, devEui, 'Sensor Antigo');
    const time = new Date(Date.now() - 2 * 60_000).toISOString();

    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({
          items: [
            {
              time,
              dev_eui: devEui,
              payload: { humidity: 40 },
              rssi: -70,
              snr: 7,
              app_id: appId,
              event_type: 'up',
            },
          ],
          next_cursor: null,
        }),
      ),
    );

    renderDetail(tenantId, appId);
    const row = (await screen.findByText(devEui)).closest('tr');
    expect(row).not.toBeNull();

    expect(
      await within(row as HTMLElement).findByText('Offline'),
    ).toBeInTheDocument();
    expect(
      within(row as HTMLElement).getByText(/humidity: 40/),
    ).toBeInTheDocument();
  });

  it('shows offline and a dash when the device has no telemetry', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    const devEui = 'aabbccddeeff1606';
    await createDevice(appId, devEui, 'Sensor Sem Dados');

    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({ items: [], next_cursor: null }),
      ),
    );

    renderDetail(tenantId, appId);
    const row = (await screen.findByText(devEui)).closest('tr');
    expect(row).not.toBeNull();

    expect(
      await within(row as HTMLElement).findByText('Offline'),
    ).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('—')).toBeInTheDocument();
  });

  it('keeps the device table when telemetry fails', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    const devEui = 'aabbccddeeff1707';
    await createDevice(appId, devEui, 'Sensor Instável');

    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({ detail: 'telemetry down' }, { status: 500 }),
      ),
    );

    renderDetail(tenantId, appId);
    const row = (await screen.findByText(devEui)).closest('tr');
    expect(row).not.toBeNull();

    expect(
      await within(row as HTMLElement).findByText('Offline'),
    ).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('—')).toBeInTheDocument();
    expect(screen.queryByText('telemetry down')).not.toBeInTheDocument();
  });
});
