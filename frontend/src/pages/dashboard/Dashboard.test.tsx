import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import { formatDate } from '../../utils/format';
import Dashboard from './Dashboard';

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

async function firstAppId(): Promise<string> {
  const tenants = (await (await fetch(`${base}/tenant`)).json()) as {
    id: string;
  }[];
  const apps = (await (
    await fetch(`${base}/tenant/${tenants[0].id}/applications`)
  ).json()) as { id: string }[];
  return apps[0].id;
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
      device_profile_id: 'profile-test',
    }),
  });
}

function renderDashboard(appId: string) {
  return render(
    <MemoryRouter initialEntries={[`/dashboard/${appId}`]}>
      <Routes>
        <Route path="/dashboard/:appId" element={<Dashboard />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Dashboard', () => {
  it('renders the telemetry chart for the selected device', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff0101');

    renderDashboard(appId);

    expect(await screen.findByTestId('telemetry-chart')).toBeInTheDocument();
    expect(screen.getByLabelText('Device')).toHaveValue('aabbccddeeff0101');
    expect(screen.getByLabelText('Métrica')).toHaveValue('temperature');
  });

  it('refetches history when the selected device changes', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff0202');
    await createDevice(appId, 'aabbccddeeff0303');

    const calls: (string | null)[] = [];
    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        const devEui = new URL(request.url).searchParams.get('dev_eui');
        calls.push(devEui);
        return HttpResponse.json({ items: [], next_cursor: null });
      }),
    );

    renderDashboard(appId);
    await screen.findByLabelText('Device');

    await userEvent.selectOptions(
      screen.getByLabelText('Device'),
      'aabbccddeeff0303',
    );

    await waitFor(() =>
      expect(calls).toContain('aabbccddeeff0303'),
    );
  });

  it('shows a retryable error when history fails', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff0404');

    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({ detail: 'telemetry down' }, { status: 500 }),
      ),
    );

    renderDashboard(appId);

    expect(await screen.findByText('telemetry down')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /tentar novamente/i }),
    ).toBeInTheDocument();
  });

  it('overlays all devices when "Todos os devices" is selected', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff0707');
    await createDevice(appId, 'aabbccddeeff0808');

    const requested: (string | null)[] = [];
    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        const devEui = new URL(request.url).searchParams.get('dev_eui');
        requested.push(devEui);
        return HttpResponse.json({
          items: [
            {
              time: '2026-01-01T00:00:00Z',
              dev_eui: devEui,
              payload: { temperature: 20 },
              rssi: -70,
              snr: 7,
              app_id: 'mock-app',
              event_type: 'up',
            },
          ],
          next_cursor: null,
        });
      }),
    );

    renderDashboard(appId);
    await screen.findByLabelText('Device');

    await userEvent.selectOptions(
      screen.getByLabelText('Device'),
      'Todos os devices',
    );

    await waitFor(() => {
      expect(requested).toContain('aabbccddeeff0707');
      expect(requested).toContain('aabbccddeeff0808');
    });
    expect(screen.getByTestId('telemetry-chart')).toBeInTheDocument();
  });

  it('shows the nickname as the device option label and dev_eui as fallback', async () => {
    const appId = await firstAppId();
    const create = (devEui: string, nickname?: string) =>
      fetch(`${base}/devices`, {
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
    await create('aabbccddeeff0909', 'Sensor Sul');
    await create('aabbccddeeff0c0c');

    renderDashboard(appId);

    expect(
      await screen.findByRole('option', { name: 'Sensor Sul' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: 'aabbccddeeff0c0c' }),
    ).toBeInTheDocument();
  });

  it('keeps other series when one device history fails', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff0a0a');
    await createDevice(appId, 'aabbccddeeff0b0b');

    server.use(
      http.get('*/api/v1/telemetry', ({ request }) => {
        const devEui = new URL(request.url).searchParams.get('dev_eui');
        if (devEui === 'aabbccddeeff0a0a') {
          return HttpResponse.json({ detail: 'boom' }, { status: 500 });
        }
        return HttpResponse.json({
          items: [
            {
              time: '2026-01-01T00:00:00Z',
              dev_eui: devEui,
              payload: { temperature: 20 },
              rssi: -70,
              snr: 7,
              app_id: 'mock-app',
              event_type: 'up',
            },
          ],
          next_cursor: null,
        });
      }),
    );

    renderDashboard(appId);
    await screen.findByLabelText('Device');
    await userEvent.selectOptions(
      screen.getByLabelText('Device'),
      'Todos os devices',
    );

    expect(await screen.findByTestId('telemetry-chart')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows a retryable error when every device history fails in Todos mode', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff0d0d');
    await createDevice(appId, 'aabbccddeeff0e0e');

    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({ detail: 'telemetry down' }, { status: 500 }),
      ),
    );

    renderDashboard(appId);
    await screen.findByLabelText('Device');
    await userEvent.selectOptions(
      screen.getByLabelText('Device'),
      'Todos os devices',
    );

    expect(await screen.findByText('telemetry down')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /tentar novamente/i }),
    ).toBeInTheDocument();
  });

  it('shows an empty state when the application has no devices', async () => {
    const tenants = (await (await fetch(`${base}/tenant`)).json()) as {
      id: string;
    }[];
    const emptyApp = (await (
      await fetch(`${base}/tenant/${tenants[0].id}/applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'App sem devices' }),
      })
    ).json()) as { id: string };

    renderDashboard(emptyApp.id);

    expect(
      await screen.findByText('Nenhum device nesta aplicação'),
    ).toBeInTheDocument();
  });

  it('shows the latest reading time, not the first item', async () => {
    const appId = await firstAppId();
    await createDevice(appId, 'aabbccddeeff1f1f');
    const reading = (time: string, temperature: number) => ({
      time,
      dev_eui: 'aabbccddeeff1f1f',
      payload: { temperature },
      rssi: -70,
      snr: 7,
      app_id: 'mock-app',
      event_type: 'up',
    });

    server.use(
      http.get('*/api/v1/telemetry', () =>
        HttpResponse.json({
          items: [
            reading('2026-01-01T00:00:00Z', 18),
            reading('2026-01-03T00:00:00Z', 21),
            reading('2026-01-02T00:00:00Z', 19),
          ],
          next_cursor: null,
        }),
      ),
    );

    renderDashboard(appId);

    const expected = `Última leitura: ${formatDate('2026-01-03T00:00:00Z')}`;
    expect(await screen.findByText(expected)).toBeInTheDocument();
  });
});
