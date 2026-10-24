import {
  afterAll,
  afterEach,
  beforeAll,
  describe,
  expect,
  it,
  vi,
} from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../mocks/handlers';
import ApplicationDetailPage from './ApplicationDetailPage';

const server = setupServer(...handlers);
const base = 'http://localhost:8000/api/v1';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  vi.useRealTimers();
});
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

  it('updates the provisioning badge as the polled status changes', async () => {
    const { tenantId, appId, appName } = await firstTenantAndApp();
    const statuses = ['PENDING', 'PROVISIONING', 'RUNNING'] as const;
    let statusIndex = 0;

    server.use(
      http.get(`*/api/v1/applications/${appId}/status`, () => {
        const status = statuses[Math.min(statusIndex, statuses.length - 1)];
        statusIndex += 1;
        return HttpResponse.json({
          app_id: appId,
          status,
          container_id: `mock-container-${appId}`,
        });
      }),
    );

    vi.useFakeTimers();
    renderDetail(tenantId, appId);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByRole('heading', { name: appName })).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(screen.getByRole('status')).toHaveTextContent('Pendente');
    expect(screen.getByRole('status')).not.toHaveClass('animate-pulse');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(screen.getByRole('status')).toHaveTextContent('Provisionando');
    expect(screen.getByRole('status')).toHaveClass('animate-pulse');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(screen.getByRole('status')).toHaveTextContent('Em execução');
    expect(screen.getByRole('status')).not.toHaveClass('animate-pulse');
  });

  it('renders the ERROR badge when polling fails the provisioning', async () => {
    const { tenantId, appId } = await firstTenantAndApp();

    server.use(
      http.get(`*/api/v1/applications/${appId}/status`, () =>
        HttpResponse.json({
          app_id: appId,
          status: 'ERROR',
          container_id: `mock-container-${appId}`,
        }),
      ),
    );

    vi.useFakeTimers();
    renderDetail(tenantId, appId);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    const badge = screen.getByRole('status');
    expect(badge).toHaveTextContent('Erro');
    expect(badge).toHaveClass('bg-red-100', 'text-red-700');
  });
});
