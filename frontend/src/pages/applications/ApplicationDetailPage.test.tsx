import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
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
      </Routes>
    </MemoryRouter>,
  );
}

async function fillDevice(
  devEui: string,
  joinEui = '1122334455667788',
  appKey = '00112233445566778899aabbccddeeff',
) {
  await screen.findByRole('option', { name: 'Perfil Teste' });
  await userEvent.type(screen.getByLabelText('DevEUI'), devEui);
  await userEvent.type(screen.getByLabelText('JoinEUI'), joinEui);
  await userEvent.type(screen.getByLabelText('AppKey'), appKey);
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

  it('rejects a short DevEUI (validation)', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    renderDetail(tenantId, appId);
    await screen.findByText('Nenhum device');

    await userEvent.click(
      screen.getAllByRole("button", { name: /novo device/i })[0],
    );
    await fillDevice('abc');
    await userEvent.click(screen.getByRole('button', { name: 'Criar' }));

    expect(
      await screen.findByText('Deve ter 16 caracteres hexadecimais'),
    ).toBeInTheDocument();
  });

  it('creates a device from a valid uppercase DevEUI', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    renderDetail(tenantId, appId);
    await screen.findByText('Nenhum device');

    await userEvent.click(
      screen.getAllByRole("button", { name: /novo device/i })[0],
    );
    await fillDevice('AABBCCDDEEFF0011');
    await userEvent.click(screen.getByRole('button', { name: 'Criar' }));

    expect(
      await screen.findByText('aabbccddeeff0011'),
    ).toBeInTheDocument();
  });

  it('surfaces the backend error when provisioning fails', async () => {
    const { tenantId, appId } = await firstTenantAndApp();
    server.use(
      http.post('*/api/v1/devices', () =>
        HttpResponse.json(
          { detail: 'Failed to provision device in ChirpStack' },
          { status: 502 },
        ),
      ),
    );
    renderDetail(tenantId, appId);
    await screen.findAllByRole('button', { name: /novo device/i });

    await userEvent.click(
      screen.getAllByRole("button", { name: /novo device/i })[0],
    );
    await fillDevice('AABBCCDDEEFF0022');
    await userEvent.click(screen.getByRole('button', { name: 'Criar' }));

    expect(
      await screen.findByText('Failed to provision device in ChirpStack'),
    ).toBeInTheDocument();
  });
});
