import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
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

async function createDevice(
  appId: string,
  devEui: string,
): Promise<{ id: string }> {
  const response = await fetch(`${base}/devices`, {
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
  return (await response.json()) as { id: string };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/devices']}>
      <Routes>
        <Route path="/devices" element={<DeviceListPage />} />
        <Route path="/onboarding" element={<div>wizard-page</div>} />
      </Routes>
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

  it('shows device UUIDs with copy actions', async () => {
    const { appId } = await firstTenantAndApp();
    const device = await createDevice(appId, 'aabbccddeeff0909');

    renderPage();

    await screen.findByText('aabbccddeeff0909');
    expect(screen.getByText(device.id)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: `Copiar UUID ${device.id}` }),
    ).toBeInTheDocument();
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

  it('surfaces an error when deleting a device fails', async () => {
    const { appId } = await firstTenantAndApp();
    await createDevice(appId, 'aabbccddeeff0404');
    server.use(
      http.delete('*/api/v1/devices/:id', () =>
        HttpResponse.json({ detail: 'delete forbidden' }, { status: 500 }),
      ),
    );

    renderPage();
    await screen.findByText('aabbccddeeff0404');

    await userEvent.click(
      screen.getByRole('button', {
        name: 'Excluir device aabbccddeeff0404',
      }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Excluir' }));

    expect(await screen.findByText('delete forbidden')).toBeInTheDocument();
  });

  it('navigates to the onboarding wizard from the Novo Device button', async () => {
    const { appId } = await firstTenantAndApp();
    await createDevice(appId, 'aabbccddeeff0505');

    renderPage();
    await screen.findByText('aabbccddeeff0505');

    await userEvent.click(screen.getByRole('button', { name: /novo device/i }));

    expect(await screen.findByText('wizard-page')).toBeInTheDocument();
  });

  it('shows the nickname and edits it from the table', async () => {
    const { appId } = await firstTenantAndApp();
    await fetch(`${base}/devices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dev_eui: 'aabbccddeeff0606',
        app_id: appId,
        join_eui: '1122334455667788',
        app_key: '00112233445566778899aabbccddeeff',
        device_profile_id: 'profile-test',
        nickname: 'Bomba 1',
      }),
    });

    renderPage();
    await screen.findByText('aabbccddeeff0606');
    expect(screen.getByText('Bomba 1')).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: 'Editar nickname aabbccddeeff0606' }),
    );
    const input = await screen.findByLabelText('Nickname');
    await userEvent.clear(input);
    await userEvent.type(input, 'Bomba 2');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('Bomba 2')).toBeInTheDocument();
  });

  it('rejects a nickname longer than 50 characters in the modal', async () => {
    const { appId } = await firstTenantAndApp();
    await fetch(`${base}/devices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dev_eui: 'aabbccddeeff1202',
        app_id: appId,
        join_eui: '1122334455667788',
        app_key: '00112233445566778899aabbccddeeff',
        device_profile_id: 'profile-test',
      }),
    });

    renderPage();
    await screen.findByText('aabbccddeeff1202');

    await userEvent.click(
      screen.getByRole('button', { name: 'Editar nickname aabbccddeeff1202' }),
    );
    const input = await screen.findByLabelText('Nickname');
    await userEvent.type(input, 'a'.repeat(51));
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(
      await screen.findByText('Máximo de 50 caracteres'),
    ).toBeInTheDocument();
  });

  it('surfaces an error when saving the nickname fails', async () => {
    const { appId } = await firstTenantAndApp();
    await fetch(`${base}/devices`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dev_eui: 'aabbccddeeff1303',
        app_id: appId,
        join_eui: '1122334455667788',
        app_key: '00112233445566778899aabbccddeeff',
        device_profile_id: 'profile-test',
        nickname: 'Antigo',
      }),
    });
    server.use(
      http.patch('*/api/v1/devices/:device_id', () =>
        HttpResponse.json({ detail: 'patch boom' }, { status: 500 }),
      ),
    );

    renderPage();
    await screen.findByText('aabbccddeeff1303');

    await userEvent.click(
      screen.getByRole('button', { name: 'Editar nickname aabbccddeeff1303' }),
    );
    const input = await screen.findByLabelText('Nickname');
    await userEvent.clear(input);
    await userEvent.type(input, 'Novo');
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }));

    expect(await screen.findByText('patch boom')).toBeInTheDocument();
  });
});
